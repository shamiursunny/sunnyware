import defusedxml.ElementTree as ET
from pathlib import Path
from .. import paths

class EditTableauFieldTool:
    name = "edit_tableau_field"
    description = "Edit a calculated field formula, filter value, or parameter in a Tableau .twb workbook. Requires file, field_name, and new_value."
    keywords = ["edit tableau", "update tableau field", "change tableau formula"]

    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The name of the Tableau file (e.g., workbook.twb or workbook.twbx)"
            },
            "field_name": {
                "type": "string",
                "description": "The exact name of the calculated field, filter, or parameter to edit"
            },
            "new_value": {
                "type": "string",
                "description": "The new formula (for calculated fields) or the new value (for filters/parameters)"
            },
            "kind": {
                "type": "string",
                "enum": ["sandbox", "workspace"],
                "description": "The location of the file (default: sandbox)"
            }
        },
        "required": ["filename", "field_name", "new_value"]
    }

    async def run(self, filename: str, field_name: str, new_value: str, kind: str = "sandbox") -> dict:
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        
        if not target.exists():
            return {"error": f"File {filename} not found in {kind}"}
        if target.suffix.lower() not in [".twb", ".twbx"]:
            return {"error": f"File {filename} is not a valid Tableau workbook (.twb or .twbx)"}

        try:
            if target.suffix.lower() == ".twbx":
                import zipfile
                with zipfile.ZipFile(target, "r") as zf:
                    twb_files = [f for f in zf.namelist() if f.endswith(".twb")]
                    if not twb_files:
                        return {"error": "No .twb file found inside the .twbx archive."}
                    xml_content = zf.read(twb_files[0]).decode("utf-8")
            else:
                xml_content = target.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}"}

        try:
            root = ET.fromstring(xml_content)
        except Exception as e:
            return {"error": f"Failed to parse Tableau XML: {str(e)}"}

        modified = False
        changes = []

        # 1. Search for Calculated Fields
        for calc in root.findall(".//calculation"):
            if calc.get("caption", "").lower() == field_name.lower() or calc.get("name", "").lower() == field_name.lower():
                old_formula = calc.get("formula", "")
                calc.set("formula", new_value)
                modified = True
                changes.append({"type": "calculation", "name": field_name, "old": old_formula, "new": new_value})

        # 2. Search for Filters
        for filt in root.findall(".//filter"):
            if filt.get("column", "").endswith(f"[{field_name}]") or filt.get("column", "") == field_name:
                gf = filt.find("groupfilter")
                if gf is not None:
                    old_val = gf.get("member", "")
                    gf.set("member", new_value)
                    modified = True
                    changes.append({"type": "filter", "name": field_name, "old": old_val, "new": new_value})

        # 3. Search for Parameters
        for param in root.findall(".//column"):
            if param.get("param-domain-type") and (param.get("caption", "").lower() == field_name.lower() or param.get("name", "").lower() == field_name.lower()):
                for member in param.findall(".//member"):
                    old_val = member.get("value", "")
                    if old_val == param.get("value"):
                        member.set("value", new_value)
                        modified = True
                        changes.append({"type": "parameter", "name": field_name, "old": old_val, "new": new_value})

        if not modified:
            return {"error": f"Could not find field, filter, or parameter named '{field_name}' in {filename}"}

        # Save changes back
        new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
        
        try:
            if target.suffix.lower() == ".twbx":
                import zipfile, io
                with zipfile.ZipFile(target, "r") as zin:
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
                        for item in zin.infolist():
                            if item.filename.endswith(".twb"):
                                zout.writestr(item, new_xml)
                            else:
                                zout.writestr(item, zin.read(item.filename))
                target.write_bytes(buf.getvalue())
            else:
                target.write_text(new_xml, encoding="utf-8")
        except Exception as e:
            return {"error": f"Failed to save changes: {str(e)}"}

        return {
            "ok": True,
            "message": f"Successfully updated {field_name} in {filename}",
            "changes": changes
        }
