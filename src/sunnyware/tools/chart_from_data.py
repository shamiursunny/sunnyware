# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Chart-from-data tool (Part 51).

Generate a PNG chart from inline JSON rows or a CSV/JSON file in the
workspace. Returns {image_base64, image_format, ...} so the WebUI
renders it inline (Part 43 wrapBareBase64 handles the magic bytes).
"""
import base64
import csv
import io
import os
import re
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt  # noqa
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


_CHART_TYPES = {"bar", "line", "scatter", "pie", "hist", "box"}
_ALLOWED_EXT = {".csv", ".tsv", ".json"}
_MAX_CHART_BYTES = 200 * 1024


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _load_rows(args: dict) -> tuple:
    """Return (rows, error). rows is a list of dicts."""
    data = args.get("data")
    if isinstance(data, list) and data:
        rows = [r for r in data if isinstance(r, dict)]
        if not rows:
            return None, "data must be a list of objects"
        return rows, None

    fname = (args.get("file") or "").strip()
    if not fname:
        return None, "provide either 'data' or 'file'"

    root = _workspace_root()
    candidate = (root / fname).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, "file must live inside the workspace"
    if not candidate.exists():
        return None, f"file not found: {fname}"

    ext = candidate.suffix.lower()
    if ext not in _ALLOWED_EXT:
        return None, f"unsupported file type: {ext}"

    try:
        if ext in (".csv", ".tsv"):
            delim = "\t" if ext == ".tsv" else ","
            with candidate.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f, delimiter=delim))
        else:
            import json as _json
            raw = candidate.read_text(encoding="utf-8")
            payload = _json.loads(raw)
            if isinstance(payload, list):
                rows = [r for r in payload if isinstance(r, dict)]
            elif isinstance(payload, dict):
                rows = [payload]
            else:
                return None, "JSON must be an array or object"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

    if not rows:
        return None, "no rows loaded"
    return rows, None


def _coerce_num(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


class ChartFromDataTool:
    name = "chart_from_data"
    description = (
        "Generate a PNG chart from data. Provide EITHER 'data' (a JSON array "
        "of row objects) OR 'file' (a CSV / TSV / JSON file in the workspace). "
        "The result includes base64 PNG bytes that render inline in the chat. "
        "Use this whenever the user asks to visualize, plot, or chart data."
    )
    parameters = {
        "data": {
            "type": "array",
            "description": "Inline array of row objects (e.g. [{\"x\":1,\"y\":2}, ...])",
            "required": False,
        },
        "file": {
            "type": "string",
            "description": "Workspace file name (CSV/TSV/JSON)",
            "required": False,
        },
        "chart_type": {
            "type": "string",
            "description": "One of: bar, line, scatter, pie, hist, box (default: bar)",
            "required": False,
        },
        "x": {
            "type": "string",
            "description": "Column name for X axis / categories (required for bar/line/scatter/pie)",
            "required": False,
        },
        "y": {
            "type": "string",
            "description": "Column name for Y axis / values (required for bar/line/scatter/box)",
            "required": False,
        },
        "title": {
            "type": "string",
            "description": "Chart title",
            "required": False,
        },
        "x_label": {"type": "string", "required": False},
        "y_label": {"type": "string", "required": False},
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_MPL:
            return {"error": "matplotlib not available in this environment"}

        rows, err = _load_rows(args)
        if err:
            return {"error": err}

        ctype = (args.get("chart_type") or "bar").strip().lower()
        if ctype not in _CHART_TYPES:
            return {"error": f"chart_type must be one of {sorted(_CHART_TYPES)}"}

        x_col = args.get("x")
        y_col = args.get("y")
        title = args.get("title") or ""
        x_label = args.get("x_label") or x_col or ""
        y_label = args.get("y_label") or y_col or ""

        # Coerce numeric y
        try:
            if ctype in ("bar", "pie"):
                if not x_col or not y_col:
                    return {"error": f"{ctype} requires both 'x' and 'y'"}
                labels = [str(r.get(x_col, "")) for r in rows]
                values = [_coerce_num(r.get(y_col)) for r in rows]
            elif ctype in ("line", "scatter", "box"):
                if not y_col:
                    return {"error": f"{ctype} requires 'y'"}
                if ctype == "box":
                    values = [_coerce_num(r.get(y_col)) for r in rows]
                    labels = None
                else:
                    x_vals = [_coerce_num(r.get(x_col)) if x_col else i
                              for i, r in enumerate(rows)]
                    values = [_coerce_num(r.get(y_col)) for r in rows]
                    labels = x_vals
            elif ctype == "hist":
                if not y_col:
                    return {"error": "hist requires 'y'"}
                values = [_coerce_num(r.get(y_col)) for r in rows]
                labels = None
            else:
                return {"error": f"unsupported chart_type: {ctype}"}
        except Exception as e:
            return {"error": f"data prep failed: {type(e).__name__}: {e}"}

        # Drop rows with bad numeric values
        if ctype == "box":
            clean = [v for v in values if v is not None]
            if not clean:
                return {"error": "no numeric values found in column '{}'".format(y_col)}
            values = clean
        elif ctype == "hist":
            clean = [v for v in values if v is not None]
            if not clean:
                return {"error": "no numeric values found in column '{}'".format(y_col)}
            values = clean
        else:
            pairs = [(l, v) for l, v in zip(labels, values) if v is not None]
            if not pairs:
                return {"error": "no numeric values found in column '{}'".format(y_col)}
            labels = [p[0] for p in pairs]
            values = [p[1] for p in pairs]

        # Render
        try:
            fig, ax = plt.subplots(figsize=(9, 5))
            if ctype == "bar":
                ax.bar(labels, values)
                ax.tick_params(axis="x", rotation=30)
            elif ctype == "line":
                ax.plot(labels, values, marker="o", linewidth=2)
            elif ctype == "scatter":
                ax.scatter(labels, values)
            elif ctype == "pie":
                ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
                ax.axis("equal")
            elif ctype == "hist":
                ax.hist(values, bins=min(30, max(5, len(values) // 3)))
            elif ctype == "box":
                ax.boxplot(values, vert=True)
                ax.set_xticks([1])
                ax.set_xticklabels([y_col or "values"])

            if title:
                ax.set_title(title)
            if x_label and ctype not in ("pie", "box", "hist"):
                ax.set_xlabel(x_label)
            if y_label and ctype not in ("pie", "box"):
                ax.set_ylabel(y_label)
            ax.grid(True, alpha=0.3, axis="y")

            buf = io.BytesIO()
            fig.tight_layout()
            fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            raw = buf.getvalue()
            if len(raw) > _MAX_CHART_BYTES:
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=60, bbox_inches="tight")
                raw = buf.getvalue()
            plt.close(fig)
        except Exception as e:
            return {"error": f"render failed: {type(e).__name__}: {e}"}

        if len(raw) > _MAX_CHART_BYTES:
            return {"error": "chart too large even at low DPI"}

        return {
            "image_base64": base64.b64encode(raw).decode("ascii"),
            "image_format": "png",
            "image_bytes": len(raw),
            "chart_type": ctype,
            "rows_plotted": len(values),
        }
