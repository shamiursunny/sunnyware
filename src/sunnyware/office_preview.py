# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
# Office document preview parsers for the full-screen viewer (Part 713).
from pathlib import Path


def parse_docx(path: Path) -> dict:
    try:
        from docx import Document
    except ImportError:
        return {"error": "python-docx not installed"}
    # Detect if the file is actually a ZIP (docx/pptx are ZIP)
    import zipfile as _zip
    _is_zip = False
    try:
        _is_zip = _zip.is_zipfile(str(path))
    except Exception:
        pass
    if not _is_zip:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            paragraphs = [{"text": line, "style": "plain"} for line in text.split("\n") if line.strip()]
            return {"ok": True, "warning": "Not a valid DOCX package — showing raw text",
                    "paragraphs": paragraphs, "tables": [],
                    "paragraph_count": len(paragraphs), "table_count": 0}
        except Exception as e:
            return {"error": f"file is not a valid docx and cannot be read as text: {e}"}
    try:
        doc = Document(str(path))
        paragraphs = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                paragraphs.append({"text": txt, "style": (p.style.name if p.style else "Normal")})
        tables = []
        for t in doc.tables:
            if not t.rows:
                continue
            headers = [c.text.strip() for c in t.rows[0].cells]
            rows = []
            for r in t.rows[1:]:
                rows.append([c.text.strip() for c in r.cells])
            tables.append({"headers": headers, "rows": rows[:500]})
        return {"ok": True, "paragraphs": paragraphs, "tables": tables,
                "paragraph_count": len(paragraphs), "table_count": len(tables)}
    except Exception as e:
        return {"error": f"docx parse failed: {type(e).__name__}: {e}"}


def parse_pptx(path: Path) -> dict:
    try:
        from pptx import Presentation
    except ImportError:
        return {"error": "python-pptx not installed"}
    import zipfile as _zip
    _is_zip = False
    try:
        _is_zip = _zip.is_zipfile(str(path))
    except Exception:
        pass
    if not _is_zip:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return {"ok": True, "warning": "Not a valid PPTX package — showing raw text",
                    "slides": [{"index": 1, "title": path.name, "texts": text.split("\n")}],
                    "slide_count": 1}
        except Exception as e:
            return {"error": f"file is not a valid pptx and cannot be read as text: {e}"}
    try:
        prs = Presentation(str(path))
        slides = []
        for i, slide in enumerate(prs.slides, start=1):
            title = ""
            texts = []
            for shape in slide.shapes:
                if not hasattr(shape, "text"):
                    continue
                tf = getattr(shape, "text_frame", None)
                if not tf:
                    continue
                tf_text = tf.text.strip()
                if not tf_text:
                    continue
                name_lower = str(shape.name).lower()
                if not title and "title" in name_lower:
                    title = tf_text
                else:
                    texts.append(tf_text)
            slides.append({"index": i, "title": title or f"Slide {i}", "texts": texts})
        return {"ok": True, "slides": slides, "slide_count": len(slides)}
    except Exception as e:
        return {"error": f"pptx parse failed: {type(e).__name__}: {e}"}


def parse_twb(path: Path) -> dict:
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        return {"error": "xml.etree not available"}
    try:
        tree = ET.parse(str(path))
        root = tree.getroot()

        datasources = []
        for ds in root.findall(".//datasource"):
            ds_info = {"name": ds.get("name", "?")}
            conns = ds.findall(".//connection")
            if conns:
                ds_info["connection"] = conns[0].get("class", "unknown")
            tables = ds.findall(".//relation")
            if tables:
                ds_info["tables"] = [t.get("table", "?") for t in tables[:20] if t.get("table")]
            datasources.append(ds_info)

        worksheets = []
        for ws in root.findall(".//worksheet"):
            ws_info = {"name": ws.get("name", "?")}
            mark = ws.find(".//mark")
            if mark is not None:
                ws_info["mark_type"] = mark.get("class", "auto")
            worksheets.append(ws_info)

        dashboards = []
        for db in root.findall(".//dashboard"):
            db_info = {"name": db.get("name", "?"), "zones": len(db.findall(".//zone"))}
            dashboards.append(db_info)

        return {"ok": True, "datasources": datasources, "worksheets": worksheets,
                "dashboards": dashboards, "file_size": path.stat().st_size}
    except Exception as e:
        return {"error": f"twb parse failed: {type(e).__name__}: {e}"}


def parse_twbx(path: Path) -> dict:
    try:
        import zipfile, tempfile
    except ImportError:
        return {"error": "zipfile not available"}
    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            names = zf.namelist()
            twb_name = next((n for n in names if n.lower().endswith(".twb")), None)
            if not twb_name:
                return {"error": "no .twb inside .twbx", "contents": names[:50]}
            with tempfile.NamedTemporaryFile(suffix=".twb", delete=False) as tmp:
                tmp.write(zf.read(twb_name))
                tmp_path = Path(tmp.name)
            try:
                result = parse_twb(tmp_path)
                result["twbx_contents"] = names[:50]
                return result
            finally:
                try: tmp_path.unlink()
                except Exception: pass
    except Exception as e:
        return {"error": f"twbx parse failed: {type(e).__name__}: {e}"}


def parse_pbix(path: Path) -> dict:
    try:
        import zipfile
    except ImportError:
        return {"error": "zipfile not available"}
    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            names = zf.namelist()
            has_report = any("Report" in n for n in names)
            has_datamodel = any("DataModel" in n or "dataModel" in n for n in names)
            has_security = any("SecurityBindings" in n for n in names)
            version = ""
            if "Version" in names:
                try: version = zf.read("Version").decode("utf-8", errors="replace").strip()
                except Exception: pass
            return {"ok": True, "valid_pbix": has_report or has_datamodel,
                    "has_report": has_report, "has_datamodel": has_datamodel,
                    "has_security_bindings": has_security, "version": version,
                    "contents": names[:50], "total_files": len(names),
                    "file_size": path.stat().st_size}
    except Exception as e:
        return {"error": f"pbix parse failed: {type(e).__name__}: {e}"}
