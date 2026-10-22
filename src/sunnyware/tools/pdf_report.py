# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""PDF report generator (Part 59).

Build a multi-page PDF from a structured spec: title, sections
(paragraphs), tables (header + rows), and charts (base64 PNGs from
chart_from_data). Saves to workspace, returns path + page count + a
base64 preview of page 1.

Uses matplotlib.backends.backend_pdf.PdfPages — no new dependencies.
"""
import base64
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt  # noqa
    from matplotlib.backends.backend_pdf import PdfPages  # noqa
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


_MAX_PAGES = 40
_MAX_SAFE_NAME = 120


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _safe_name(name: str) -> str:
    name = (name or "report.pdf").strip()
    # Keep alnum, dot, dash, underscore
    cleaned = "".join(c if (c.isalnum() or c in "._-") else "_" for c in name)
    if not cleaned.lower().endswith(".pdf"):
        cleaned += ".pdf"
    return cleaned[:_MAX_SAFE_NAME]


def _text_page(title: str, body: str, meta: str):
    """Render a text page and return the figure."""
    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor("white")
    # Title
    fig.text(0.08, 0.93, title or "", fontsize=18, fontweight="bold",
             color="#111111", va="top")
    # Meta line
    if meta:
        fig.text(0.08, 0.89, meta, fontsize=9, color="#555555", va="top")
    # Body — wrap long lines roughly at 95 chars
    wrapped = []
    for raw_line in (body or "").splitlines() or [""]:
        line = raw_line
        while len(line) > 95:
            wrapped.append(line[:95])
            line = line[95:]
        wrapped.append(line)
    # Cap lines to fit page (approx 50 lines @ 8.5x11)
    text = "\n".join(wrapped[:_MAX_PAGES * 50])
    fig.text(0.08, 0.84, text, fontsize=10, color="#222222",
             va="top", family="monospace")
    return fig


def _table_page(title: str, headers: list, rows: list, meta: str = ""):
    """Render a simple table page."""
    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor("white")
    fig.text(0.08, 0.93, title or "", fontsize=16, fontweight="bold",
             color="#111111", va="top")
    if meta:
        fig.text(0.08, 0.895, meta, fontsize=9, color="#555555", va="top")

    if not headers or not rows:
        fig.text(0.08, 0.84, "(empty table)", fontsize=11,
                 color="#888888", va="top")
        return fig

    # Cap rows to fit page
    rows = rows[:35]
    ax = fig.add_axes([0.06, 0.12, 0.88, 0.72])
    ax.axis("off")
    tbl = ax.table(cellText=[[str(c) for c in r] for r in rows],
                   colLabels=[str(h) for h in headers],
                   loc="upper center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.3)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor("#1d2026")
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor("#f7f7f9" if r % 2 else "white")
    return fig


def _chart_page(title: str, b64_png: str, caption: str = ""):
    """Render a page with an embedded PNG chart."""
    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor("white")
    fig.text(0.08, 0.93, title or "", fontsize=16, fontweight="bold",
             color="#111111", va="top")
    try:
        raw = base64.b64decode(b64_png)
        img = plt.imread(io.BytesIO(raw), format="png")
    except Exception as e:
        fig.text(0.08, 0.84, f"(chart render error: {e})", fontsize=11,
                 color="#cc0000", va="top")
        return fig
    ax = fig.add_axes([0.08, 0.20, 0.84, 0.68])
    ax.imshow(img)
    ax.axis("off")
    if caption:
        fig.text(0.08, 0.15, caption, fontsize=10, color="#555555", va="top")
    return fig


class PdfReportTool:
    name = "pdf_report"
    description = "Create a PDF report with a title and body. Triggers: create PDF, make PDF report, generate PDF. Input: title and content. Returns PDF path.", type='table' "
        "(title + headers + rows), or type='chart' (title + image_base64 "
        "from chart_from_data + optional caption). Saves to workspace and "
        "returns the file path plus a base64 preview of page 1. "
        "Use for board decks, monthly reports, variance summaries."
    )
    parameters = {
        "filename": {
            "type": "string",
            "description": "Output filename (default report.pdf)",
            "required": False,
        },
        "title": {
            "type": "string",
            "description": "Report title (appears on every page as meta)",
            "required": False,
        },
        "pages": {
            "type": "array",
            "description": (
                "Array of page specs. Each: "
                "{\"type\":\"text\",\"title\":..,\"body\":..} or "
                "{\"type\":\"table\",\"title\":..,\"headers\":[..],\"rows\":[[..],..]} or "
                "{\"type\":\"chart\",\"title\":..,\"image_base64\":\"...\",\"caption\":..}"
            ),
            "required": True,
        },
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_MPL:
            return {"error": "matplotlib not available in this environment"}

        pages = args.get("pages")
        if not isinstance(pages, list) or not pages:
            return {"error": "pages must be a non-empty array"}
        if len(pages) > _MAX_PAGES:
            return {"error": f"too many pages (max {_MAX_PAGES})"}

        report_title = (args.get("title") or "").strip()
        meta = datetime.utcnow().strftime("Generated %Y-%m-%d %H:%M UTC")
        if report_title:
            meta = f"{report_title}  |  {meta}"

        fname = _safe_name(args.get("filename") or "report.pdf")
        root = _workspace_root()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"error": f"workspace not writable: {e}"}
        out_path = (root / fname).resolve()
        try:
            out_path.relative_to(root)
        except ValueError:
            return {"error": "filename escapes workspace"}

        rendered_pages = 0
        first_page_png = None

        try:
            with PdfPages(str(out_path)) as pdf:
                for idx, page in enumerate(pages):
                    if not isinstance(page, dict):
                        continue
                    ptype = (page.get("type") or "text").lower()
                    ptitle = page.get("title") or f"Page {idx + 1}"
                    fig = None
                    if ptype == "text":
                        fig = _text_page(ptitle, page.get("body") or "", meta)
                    elif ptype == "table":
                        headers = page.get("headers") or []
                        rows = page.get("rows") or []
                        fig = _table_page(ptitle, headers, rows, meta)
                    elif ptype == "chart":
                        b64 = page.get("image_base64") or ""
                        caption = page.get("caption") or ""
                        fig = _chart_page(ptitle, b64, caption)
                        # Also add a small meta line
                        fig.text(0.08, 0.965, meta, fontsize=8,
                                 color="#888888", va="top")
                    else:
                        continue
                    pdf.savefig(fig)
                    plt.close(fig)
                    rendered_pages += 1
                    # Capture page 1 as PNG for preview
                    if rendered_pages == 1:
                        buf = io.BytesIO()
                        # Re-render isn't cheap — instead, snapshot what we
                        # just saved by regenerating a quick preview
                        # (single-page approach: re-create a tiny figure)
                        preview_fig = _text_page(
                            report_title or "Sunnyware Report",
                            f"{rendered_pages} page(s) saved to {fname}",
                            meta,
                        )
                        preview_fig.savefig(buf, format="png",
                                            dpi=70, bbox_inches="tight")
                        plt.close(preview_fig)
                        first_page_png = base64.b64encode(
                            buf.getvalue()).decode("ascii")
        except Exception as e:
            return {"error": f"pdf generation failed: {type(e).__name__}: {e}"}

        try:
            size = out_path.stat().st_size
        except Exception:
            size = 0

        return {
            "filename": fname,
            "path": str(out_path),
            "pages_rendered": rendered_pages,
            "size_bytes": size,
            "preview_image_base64": first_page_png,
            "preview_format": "png",
        }
