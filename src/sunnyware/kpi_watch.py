# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""KPI watch core logic (Part 75)."""
import re
import time
from typing import Optional
from . import state as app_state


_VALID_COMPARISONS = {"lt", "gt", "le", "ge", "eq", "ne"}
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _parse_number(text: str, pattern: Optional[str] = None) -> Optional[float]:
    if not text:
        return None
    if pattern:
        try:
            m = re.search(pattern, text)
            if m:
                raw = m.group(1) if m.groups() else m.group(0)
                return float(str(raw).replace(",", ""))
        except Exception:
            pass
    m = _NUMBER_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _compare(value: float, op: str, threshold: float) -> bool:
    if op == "lt": return value < threshold
    if op == "gt": return value > threshold
    if op == "le": return value <= threshold
    if op == "ge": return value >= threshold
    if op == "eq": return abs(value - threshold) < 1e-9
    if op == "ne": return abs(value - threshold) >= 1e-9
    return False


async def add_watch(kpi_name, check_prompt, comparison, threshold_value,
                    extract_pattern=None, interval_seconds=3600,
                    notify_email=""):
    kpi_name = (kpi_name or "").strip()
    check_prompt = (check_prompt or "").strip()
    comparison = (comparison or "").strip().lower()

    if not kpi_name or len(kpi_name) > 100:
        return {"error": "kpi_name must be 1-100 chars"}
    if not check_prompt or len(check_prompt) > 2000:
        return {"error": "check_prompt must be 1-2000 chars"}
    if comparison not in _VALID_COMPARISONS:
        return {"error": "comparison must be one of " + str(sorted(_VALID_COMPARISONS))}
    if interval_seconds < 60 or interval_seconds > 604800:
        return {"error": "interval_seconds must be 60-604800"}

    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO kpi_watches
                   (kpi_name, check_prompt, comparison, threshold_value,
                    extract_pattern, interval_seconds, enabled, notify_email)
                   VALUES ($1, $2, $3, $4, $5, $6, TRUE, $7)
                   ON CONFLICT (kpi_name) DO UPDATE SET
                     check_prompt = EXCLUDED.check_prompt,
                     comparison = EXCLUDED.comparison,
                     threshold_value = EXCLUDED.threshold_value,
                     extract_pattern = EXCLUDED.extract_pattern,
                     interval_seconds = EXCLUDED.interval_seconds,
                     notify_email = EXCLUDED.notify_email,
                     enabled = TRUE
                   RETURNING id""",
                kpi_name, check_prompt, comparison,
                float(threshold_value), extract_pattern,
                int(interval_seconds), (notify_email or "").strip() or None)
            return {"ok": True, "id": int(row["id"]), "kpi_name": kpi_name}
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)}


async def list_watches(include_events: bool = False, events_limit: int = 5):
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, kpi_name, check_prompt, comparison,
                          threshold_value, extract_pattern, enabled,
                          interval_seconds, last_run_at, last_value,
                          last_status, last_error, created_at,
                          notify_email
                   FROM kpi_watches ORDER BY created_at DESC""")
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)}

    watches = []
    for r in rows:
        watches.append({
            "id": int(r["id"]),
            "kpi_name": r["kpi_name"],
            "check_prompt": r["check_prompt"],
            "comparison": r["comparison"],
            "threshold_value": float(r["threshold_value"]) if r["threshold_value"] is not None else None,
            "extract_pattern": r["extract_pattern"],
            "enabled": bool(r["enabled"]),
            "interval_seconds": int(r["interval_seconds"]),
            "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
            "last_value": float(r["last_value"]) if r["last_value"] is not None else None,
            "last_status": r["last_status"],
            "last_error": r["last_error"],
            "notify_email": r["notify_email"] or "",
        })

    if include_events and watches:
        try:
            async with pool.acquire() as conn:
                for w in watches:
                    ev_rows = await conn.fetch(
                        """SELECT status, value, threshold_value, comparison,
                                  answer_preview, error, created_at
                           FROM kpi_watch_events
                           WHERE watch_id = $1
                           ORDER BY created_at DESC LIMIT $2""",
                        w["id"], int(events_limit))
                    w["recent_events"] = [{
                        "status": e["status"],
                        "value": float(e["value"]) if e["value"] is not None else None,
                        "threshold_value": float(e["threshold_value"]) if e["threshold_value"] is not None else None,
                        "comparison": e["comparison"],
                        "answer_preview": e["answer_preview"],
                        "error": e["error"],
                        "created_at": e["created_at"].isoformat() if e["created_at"] else None,
                    } for e in ev_rows]
        except Exception as e:
            return {"watches": watches, "count": len(watches),
                    "warning": "events fetch failed: " + str(e)}

    return {"watches": watches, "count": len(watches)}


async def run_watch(watch_row: dict):
    from . import orchestrator as _orch

    wid = int(watch_row["id"])
    kpi_name = watch_row["kpi_name"]
    prompt = watch_row["check_prompt"]
    op = watch_row["comparison"]
    threshold = float(watch_row["threshold_value"])
    pattern = watch_row.get("extract_pattern")

    t0 = time.time()
    try:
        result = await _orch.run_agent(prompt)
        answer = (result.get("answer") or "").strip()
        value = _parse_number(answer, pattern)
        latency_ms = int((time.time() - t0) * 1000)

        if value is None:
            status = "error"
            err = "could not parse number from answer"
        else:
            status = "breach" if _compare(value, op, threshold) else "ok"
            err = None
    except Exception as e:
        value = None
        status = "error"
        err = type(e).__name__ + ": " + str(e)
        answer = ""
        latency_ms = int((time.time() - t0) * 1000)

    should_log = status in ("breach", "error")
    pool = app_state.get_pool()
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                if should_log:
                    await conn.execute(
                        """INSERT INTO kpi_watch_events
                           (watch_id, kpi_name, status, value, threshold_value,
                            comparison, answer_preview, error)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                        wid, kpi_name, status, value, threshold, op,
                        (answer or "")[:500], err)
                await conn.execute(
                    """UPDATE kpi_watches SET
                         last_run_at = NOW(),
                         last_value = $1,
                         last_status = $2,
                         last_error = $3
                       WHERE id = $4""",
                    value, status, err, wid)
        except Exception as e:
            return {"error": "db write failed: " + str(e),
                    "status": status, "value": value}

    # Part 76: send email on breach if notify_email configured
    email_result = None
    if status == "breach":
        notify_email = (watch_row.get("notify_email") or "").strip()
        if notify_email:
            try:
                from . import email_send as _em
                if _em.is_configured():
                    subject = "[KPI BREACH] " + kpi_name
                    body = (
                        "KPI watch breach detected.\n\n"
                        "KPI:       " + kpi_name + "\n"
                        "Value:     " + str(value) + "\n"
                        "Threshold: " + op + " " + str(threshold) + "\n"
                        "Answer:    " + (answer or "")[:400] + "\n"
                        "Latency:   " + str(latency_ms) + " ms\n"
                    )
                    email_result = await _em.send_email(
                        to=[notify_email],
                        subject=subject,
                        body=body,
                    )
                else:
                    email_result = {"error": "SMTP not configured"}
            except Exception as e:
                email_result = {"error": type(e).__name__ + ": " + str(e)}

    return {
        "kpi_name": kpi_name,
        "status": status,
        "value": value,
        "threshold_value": threshold,
        "comparison": op,
        "latency_ms": latency_ms,
        "answer_preview": (answer or "")[:200],
        "error": err,
        "email_sent": bool(email_result and email_result.get("ok")),
        "email_error": email_result.get("error") if email_result else None,
    }


async def run_all(enabled_only: bool = True):
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}

    try:
        async with pool.acquire() as conn:
            if enabled_only:
                rows = await conn.fetch("SELECT * FROM kpi_watches WHERE enabled = TRUE ORDER BY id")
            else:
                rows = await conn.fetch("SELECT * FROM kpi_watches ORDER BY id")
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)}

    results = []
    for r in rows:
        try:
            res = await run_watch(dict(r))
        except Exception as e:
            res = {"kpi_name": r["kpi_name"], "status": "error",
                   "error": type(e).__name__ + ": " + str(e)}
        results.append(res)

    breached = [x for x in results if x.get("status") == "breach"]
    errored = [x for x in results if x.get("status") == "error"]
    return {
        "run_count": len(results),
        "breach_count": len(breached),
        "error_count": len(errored),
        "breaches": breached,
        "results": results,
    }
