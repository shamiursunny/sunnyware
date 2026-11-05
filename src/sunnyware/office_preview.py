# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
# Office document preview parsers for the full-screen viewer (Part 713).
from pathlib import Path


# ── Part 714: Legacy .doc / .ppt support via LibreOffice + fallback ──

def _libreoffice_convert(input_path, output_ext):
    """Convert any office file to output_ext via LibreOffice headless."""
    import subprocess, tempfile
    outdir = Path(tempfile.mkdtemp(prefix="lo_out_"))
    profile = Path(tempfile.mkdtemp(prefix="lo_prof_"))
    try:
        cmd = [
            "soffice", "--headless", "--norestore",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to", output_ext,
            "--outdir", str(outdir),
            str(input_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if r.returncode != 0:
            raise RuntimeError(f"lo exit {r.returncode}: {r.stderr[:200]}")
        expected = outdir / (input_path.stem + "." + output_ext)
        if expected.exists():
            return expected
        files = list(outdir.iterdir())
        if not files:
            raise RuntimeError("lo produced no output")
        return files[0]
    finally:
        pass


def parse_doc(path: Path) -> dict:
    """Parse legacy .doc. Try LibreOffice -> antiword."""
    lo_error = None
    try:
        converted = _libreoffice_convert(path, "docx")
        result = parse_docx(converted)
        if result.get("ok"):
            result["engine"] = "libreoffice"
            return result
        lo_error = result.get("error", "unknown parse error")
    except FileNotFoundError:
        lo_error = "libreoffice (soffice) not installed"
    except Exception as e:
        lo_error = f"{type(e).__name__}: {e}"

    try:
        import subprocess
        r = subprocess.run(["antiword", str(path)], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            paragraphs = [{"text": line, "style": "plain"} for line in r.stdout.split("\n") if line.strip()]
            return {
                "ok": True,
                "warning": f"LibreOffice unavailable ({lo_error}) - showing text-only via antiword",
                "paragraphs": paragraphs, "tables": [],
                "paragraph_count": len(paragraphs), "table_count": 0,
                "engine": "antiword",
            }
        return {"error": f"antiword failed: {(r.stderr or 'no output')[:200]}"}
    except FileNotFoundError:
        return {"error": f"no .doc engine available. LO: {lo_error}. antiword: not installed"}
    except Exception as e:
        return {"error": f"all .doc engines failed. LO: {lo_error}. antiword: {e}"}


def parse_ppt(path: Path) -> dict:
    """Parse legacy .ppt. Try LibreOffice -> catppt."""
    lo_error = None
    try:
        converted = _libreoffice_convert(path, "pptx")
        result = parse_pptx(converted)
        if result.get("ok"):
            result["engine"] = "libreoffice"
            return result
        lo_error = result.get("error", "unknown parse error")
    except FileNotFoundError:
        lo_error = "libreoffice (soffice) not installed"
    except Exception as e:
        lo_error = f"{type(e).__name__}: {e}"

    try:
        import subprocess
        r = subprocess.run(["catppt", str(path)], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            return {
                "ok": True,
                "warning": f"LibreOffice unavailable ({lo_error}) - showing text-only via catppt",
                "slides": [{"index": 1, "title": path.name, "texts": r.stdout.split("\n")}],
                "slide_count": 1,
                "engine": "catppt",
            }
        return {"error": f"catppt failed: {(r.stderr or 'no output')[:200]}"}
    except FileNotFoundError:
        return {"error": f"no .ppt engine available. LO: {lo_error}. catppt: not installed"}
    except Exception as e:
        return {"error": f"all .ppt engines failed. LO: {lo_error}. catppt: {e}"}



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




# ── Part 715: Legacy .xls support via LibreOffice ──

def _extract_sheets_from_xlsx(xlsx_path: Path) -> dict:
    """Shared helper: extract sheets from an xlsx file via openpyxl."""
    import openpyxl
    wb = openpyxl.load_workbook(str(xlsx_path), data_only=True, read_only=True)
    sheets = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows_iter = ws.iter_rows(values_only=True)
        try:
            headers_row = next(rows_iter, None)
        except StopIteration:
            headers_row = None
        if not headers_row:
            sheets[sheet_name] = {"headers": [], "rows": []}
            continue
        headers = [str(h) if h is not None else f"col{i+1}" for i, h in enumerate(headers_row)]
        rows = []
        for r in rows_iter:
            if all(c is None for c in r):
                continue
            row_dict = {}
            for i, h in enumerate(headers):
                row_dict[h] = r[i] if i < len(r) else None
            rows.append(row_dict)
        sheets[sheet_name] = {"headers": headers, "rows": rows[:2000]}
    wb.close()
    return sheets


def _extract_sheets_from_xlrd(xls_path: Path) -> dict:
    """Extract sheets from a BIFF .xls file via xlrd."""
    import xlrd
    book = xlrd.open_workbook(str(xls_path))
    sheets = {}
    for sheet_name in book.sheet_names():
        ws = book.sheet_by_name(sheet_name)
        if ws.nrows == 0:
            sheets[sheet_name] = {"headers": [], "rows": []}
            continue
        headers = [str(c.value) for c in ws.row(0)]
        rows = []
        for r_idx in range(1, min(ws.nrows, 2001)):
            row_vals = ws.row(r_idx)
            row_dict = {}
            for i, h in enumerate(headers):
                v = row_vals[i].value if i < len(row_vals) else None
                row_dict[h] = v
            rows.append(row_dict)
        sheets[sheet_name] = {"headers": headers, "rows": rows[:2000]}
    return sheets


def _detect_office_magic(path: Path) -> str:
    """Detect file magic bytes: 'zip' (XLSX/DOCX/PPTX), 'ole' (BIFF/XLS/DOC/PPT), or 'unknown'."""
    try:
        with open(str(path), "rb") as f:
            head = f.read(8)
    except Exception:
        return "unknown"
    if head[:4] == b"PK\x03\x04":
        return "zip"
    if head[:4] == b"\xd0\xcf\x11\xe0":
        return "ole"
    return "unknown"


def parse_xls(path: Path) -> dict:
    """Parse .xls file. Detects real format by magic bytes and routes accordingly."""
    magic = _detect_office_magic(path)

    # Strategy A: ZIP magic -> it's really XLSX content, copy to temp .xlsx and read
    if magic == "zip":
        import tempfile, shutil
        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copy(str(path), str(tmp_path))
            try:
                sheets = _extract_sheets_from_xlsx(tmp_path)
                return {"ok": True, "name": path.name, "sheets": sheets,
                        "engine": "xlsx-in-xls-extension"}
            finally:
                try: tmp_path.unlink()
                except Exception: pass
        except Exception as e:
            return {"error": f"XLSX content parse failed: {type(e).__name__}: {str(e)[:200]}"}

    # Strategy B: OLE/BIFF magic -> real legacy .xls, use xlrd
    if magic == "ole":
        try:
            sheets = _extract_sheets_from_xlrd(path)
            return {"ok": True, "name": path.name, "sheets": sheets, "engine": "xlrd"}
        except ImportError:
            xlrd_err = "xlrd not installed"
        except Exception as e:
            xlrd_err = f"{type(e).__name__}: {str(e)[:150]}"
        # Fall back to LibreOffice
        try:
            converted = _libreoffice_convert(path, "xlsx")
            sheets = _extract_sheets_from_xlsx(converted)
            return {"ok": True, "name": path.name, "sheets": sheets, "engine": "libreoffice"}
        except Exception as e:
            return {"error": f"BIFF parse failed. xlrd: {xlrd_err} | LibreOffice: {type(e).__name__}: {str(e)[:150]}"}

    # Strategy C: Unknown magic -> try all engines
    errors = []
    try:
        sheets = _extract_sheets_from_xlrd(path)
        return {"ok": True, "name": path.name, "sheets": sheets, "engine": "xlrd-fallback"}
    except Exception as e:
        errors.append(f"xlrd: {type(e).__name__}: {str(e)[:100]}")
    try:
        converted = _libreoffice_convert(path, "xlsx")
        sheets = _extract_sheets_from_xlsx(converted)
        return {"ok": True, "name": path.name, "sheets": sheets, "engine": "libreoffice-fallback"}
    except Exception as e:
        errors.append(f"LibreOffice: {type(e).__name__}: {str(e)[:100]}")
    return {"error": f"Unknown file format. {' | '.join(errors)}"}



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
