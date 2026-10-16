# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 137c: scheduled eval suite run.

Registered by jobs.register_all() only when SUNNYWARE_EVAL_INTERVAL_HOURS > 0.
Each execution calls evals.run_suite(default_call_fn) and logs the summary.
"""


async def run():
    from ..runtime import log
    from .. import evals as E
    try:
        run = await E.run_suite(
            E.default_call_fn,
            triggered_by="scheduler",
        )
        s = run.get("summary") or {}
        try:
            log.info(
                "evals_scheduled_run",
                run_id=run.get("run_id"),
                total=s.get("total"),
                passed=s.get("passed"),
                failed=s.get("failed"),
                errors=s.get("errors"),
                score=s.get("score"),
                duration_ms=run.get("duration_ms"),
            )
        except Exception:
            pass
        return {
            "run_id": run.get("run_id"),
            "summary": s,
        }
    except Exception as e:
        try:
            log.error(
                "evals_scheduled_error",
                err=f"{type(e).__name__}: {e}",
            )
        except Exception:
            pass
        return {"error": f"{type(e).__name__}: {e}"}
