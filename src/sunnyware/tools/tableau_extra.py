import xml.etree.ElementTree as ET
from pathlib import Path
from .. import paths

class AddTableauFilterTool:
    name = "add_tableau_filter"
    description = "Add a filter to a Tableau worksheet."
    keywords = ["add tableau filter", "filter tableau"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "worksheet": {"type": "string"},
            "field": {"type": "string"},
            "value": {"type": "string"}
        },
        "required": ["filename", "worksheet", "field", "value"]
    }

    async def run(self, filename: str, worksheet: str, field: str, value: str, kind: str = "sandbox") -> dict:
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists(): return {"error": "File not found"}
        
        root = ET.fromstring(target.read_text(encoding="utf-8"))
        for ws in root.findall(".//worksheet"):
            if ws.get("name", "").lower() == worksheet.lower():
                filt = ET.SubElement(ws, "filter", column=f"[{field}]")
                ET.SubElement(filt, "groupfilter", member=value, function="member")
                break
        else:
            return {"error": f"Worksheet '{worksheet}' not found"}
            
        target.write_text(ET.tostring(root, encoding="utf-8").decode("utf-8"), encoding="utf-8")
        return {"ok": True, "message": f"Added filter {field}={value} to {worksheet}"}

class RemoveTableauFieldTool:
    name = "remove_tableau_field"
    description = "Remove a calculated field from a Tableau workbook."
    keywords = ["remove tableau field", "delete tableau calc"]
    parameters = {
        "type": "object",
        "properties": {"filename": {"type": "string"}, "field_name": {"type": "string"}},
        "required": ["filename", "field_name"]
    }

    async def run(self, filename: str, field_name: str, kind: str = "sandbox") -> dict:
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists(): return {"error": "File not found"}
        
        root = ET.fromstring(target.read_text(encoding="utf-8"))
        removed = 0
        for parent in root.findall(".//datasource"):
            for calc in parent.findall("calculation"):
                if calc.get("caption", "").lower() == field_name.lower():
                    parent.remove(calc)
                    removed += 1
        if removed == 0: return {"error": f"Field '{field_name}' not found"}
        
        target.write_text(ET.tostring(root, encoding="utf-8").decode("utf-8"), encoding="utf-8")
        return {"ok": True, "message": f"Removed {removed} fields named {field_name}"}

class ExtractPbixAssetsTool:
    name = "extract_pbix_assets"
    description = "Extract embedded data and images from a Power BI .pbix file."
    keywords = ["extract pbix", "power bi assets"]
    parameters = {
        "type": "object",
        "properties": {"filename": {"type": "string"}},
        "required": ["filename"]
    }

    async def run(self, filename: str, kind: str = "sandbox") -> dict:
        import zipfile
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists(): return {"error": "File not found"}
        
        try:
            with zipfile.ZipFile(target, "r") as zf:
                files = zf.namelist()
                assets = [f for f in files if f.startswith("Data") or f.startswith("CustomVisuals") or f.startswith("Report/StaticResources")]
                return {"ok": True, "total_files": len(files), "assets": assets[:20]}
        except Exception as e:
            return {"error": str(e)}
