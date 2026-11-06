import asyncio
import types
from pathlib import Path
from . import _sandbox
from .. import paths

# Global dictionary to hold persistent sessions
_SESSIONS = {}

class PythonSessionTool:
    name = "python_session"
    description = "Run Python code in a persistent session. Variables (like DataFrames) persist across messages."
    keywords = ["persistent python", "python session", "run code in session"]
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "session_id": {"type": "string", "description": "Session ID", "default": "default"}
        },
        "required": ["code"]
    }

    async def run(self, code: str, session_id: str = "default", kind: str = "sandbox") -> dict:
        # 1. Get or create the session globals
        if session_id not in _SESSIONS:
            _SESSIONS[session_id] = _sandbox.build_globals()
            
            # --- SMART PATH RESOLUTION PROXY ---
            import pandas as real_pd
            
            pd_proxy = types.ModuleType("pandas")
            pd_proxy.__dict__.update(real_pd.__dict__)
            
            def _patched_read(file_method):
                def wrapper(filepath, *args, **kwargs):
                    if isinstance(filepath, str):
                        p = Path(filepath)
                        if not p.exists():
                            # 1. Check Workspace
                            ws_file = paths.workspace() / p.name
                            if ws_file.exists():
                                filepath = str(ws_file)
                            else:
                                # 2. Check Sandbox
                                sb_file = paths.sandbox() / p.name
                                if sb_file.exists():
                                    filepath = str(sb_file)
                    return file_method(filepath, *args, **kwargs)
                return wrapper
            
            pd_proxy.read_csv = _patched_read(real_pd.read_csv)
            pd_proxy.read_excel = _patched_read(real_pd.read_excel)
            _SESSIONS[session_id]["pd"] = pd_proxy
            # -----------------------------------

        g = _SESSIONS[session_id]
        
        # 2. Validate the code
        errors = _sandbox.validate(code)
        if errors:
            return {"error": "code rejected", "reasons": errors}
            
        # 3. Auto-capture last expression (IPython-style heuristic)
        code_stripped = code.strip()
        if code_stripped and "\n" not in code_stripped:
            # Don't auto-assign if it's a control flow or assignment
            if not code_stripped.startswith(("import ", "from ", "def ", "class ", "if ", "for ", "while ", "try ", "with ", "return ", "print(", "result =")):
                # Simple check to see if it's a basic assignment like "df = ..."
                if "=" not in code_stripped.split("(")[0]:
                    code = f"result = {code_stripped}"

        # 4. Execute in a thread
        res = await asyncio.to_thread(_sandbox.exec_code, code, g)
        
        # 4. Capture charts
        chart = _sandbox.capture_chart(g.get("plt"))
        if chart:
            res.update(chart)
            
        return res
