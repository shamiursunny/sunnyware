# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 124: deterministic auto-narrative from tabular data.

Inspired by Hebbia Matrix ("table first, narrative second"). Given a
JSON array of row objects, produce a plain-English summary using only
pure-Python statistics — no LLM, no network, deterministic output.
"""
import json
import math


def _is_num(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if not s:
            return False
        try:
            float(s)
            return True
        except Exception:
            return False
    return False


def _to_num(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return float(v.strip().replace(",", ""))
    return float(v)


def _stats(nums):
    if not nums:
        return None
    n = len(nums)
    total = sum(nums)
    avg = total / n
    mn = min(nums)
    mx = max(nums)
    # Trend: first half avg vs second half avg (only meaningful if n >= 4)
    trend = None
    if n >= 4:
        half = n // 2
        a = sum(nums[:half]) / half
        b = sum(nums[half:]) / (n - half)
        if a == 0:
            trend = "flat"
        else:
            pct = (b - a) / abs(a)
            if pct > 0.05:
                trend = "up"
            elif pct < -0.05:
                trend = "down"
            else:
                trend = "flat"
    return {"count": n, "sum": total, "avg": avg, "min": mn, "max": mx,
            "trend": trend}


def _fmt(x):
    if isinstance(x, float):
        if x == int(x) and abs(x) < 1e15:
            return f"{int(x):,}"
        return f"{x:,.2f}"
    return f"{x:,}"


def build_narrative(rows, title="Dataset"):
    """rows: list of dicts. Returns (narrative_str, summary_dict)."""
    if not isinstance(rows, list) or not rows:
        return ("No rows to summarize.", {"row_count": 0})

    if not all(isinstance(r, dict) for r in rows):
        return ("Rows must be objects (dicts).", {"row_count": 0})

    n = len(rows)
    # Union of keys (preserve first-seen order)
    keys = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    # Column classification
    numeric_cols = {}
    cat_cols = {}
    for k in keys:
        nums = []
        is_num_col = True
        for r in rows:
            v = r.get(k)
            if v is None or v == "":
                continue
            if _is_num(v):
                nums.append(_to_num(v))
            else:
                is_num_col = False
                break
        if is_num_col and len(nums) >= max(1, n // 2):
            numeric_cols[k] = _stats(nums)
        else:
            # Categorical: value counts
            counts = {}
            for r in rows:
                v = r.get(k)
                if v is None or v == "":
                    continue
                sv = str(v)
                counts[sv] = counts.get(sv, 0) + 1
            top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
            cat_cols[k] = {"unique": len(counts), "top": top}

    lines = [f"{title}: {n} rows × {len(keys)} columns."]

    # Numeric summaries
    if numeric_cols:
        lines.append("Numeric columns:")
        for k, s in numeric_cols.items():
            trend_txt = ""
            if s["trend"] == "up":
                trend_txt = " (trending up)"
            elif s["trend"] == "down":
                trend_txt = " (trending down)"
            lines.append(
                f"  - {k}: sum={_fmt(s['sum'])}, avg={_fmt(s['avg'])}, "
                f"min={_fmt(s['min'])}, max={_fmt(s['max'])} "
                f"across {s['count']} values{trend_txt}."
            )

    # Categorical summaries
    if cat_cols:
        lines.append("Categorical columns:")
        for k, s in cat_cols.items():
            if not s["top"]:
                lines.append(f"  - {k}: all values empty.")
                continue
            top_str = ", ".join(f"{v} ({c})" for v, c in s["top"][:3])
            lines.append(
                f"  - {k}: {s['unique']} unique value"
                f"{'s' if s['unique'] != 1 else ''}. Top: {top_str}."
            )

    if not numeric_cols and not cat_cols:
        lines.append("No analyzable columns detected.")

    narrative = "\n".join(lines)
    summary = {
        "row_count": n,
        "column_count": len(keys),
        "columns": keys,
        "numeric_summary": {k: v for k, v in numeric_cols.items()},
        "categorical_summary": {
            k: {"unique": v["unique"], "top": v["top"]}
            for k, v in cat_cols.items()
        },
    }
    return narrative, summary


class NarrateTableTool:
    name = "narrate_table"
    description = "Convert a 2D table into a natural-language narrative. Triggers: narrate table, explain table, describe data. Input: 2D table. Returns prose description.". Pure Python statistics — no LLM, deterministic. "
        "Summarizes numeric columns (sum/avg/min/max/trend) and categorical "
        "columns (unique count, top values). Use after python_eval to turn "
        "a computed table into a client-ready paragraph."
    )
    parameters = {
        "rows": {
            "type": "string",
            "description": "JSON array of objects, e.g. '[{\"a\":1,\"b\":\"x\"}, ...]'",
            "required": True,
        },
        "title": {
            "type": "string",
            "description": "Optional title shown at the start of the narrative",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        raw = args.get("rows")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception as e:
                return {"error": "rows is not valid JSON: " + str(e)}
        if not isinstance(raw, list):
            return {"error": "rows must be a JSON array of objects"}
        title = (args.get("title") or "Dataset").strip() or "Dataset"
        try:
            narrative, summary = build_narrative(raw, title=title)
        except Exception as e:
            return {"error": type(e).__name__ + ": " + str(e)}
        return {"narrative": narrative, "summary": summary}
