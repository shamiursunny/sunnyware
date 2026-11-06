import asyncio
from . import _sandbox

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
        
        g = _SESSIONS[session_id]
        
        # 2. Validate the code
        errors = _sandbox.validate(code)
        if errors:
            return {"error": "code rejected", "reasons": errors}
            
        # 3. Execute in a thread to avoid blocking the event loop
        res = await asyncio.to_thread(_sandbox.exec_code, code, g)
        
        # 4. Capture any matplotlib/plotly charts
        chart = _sandbox.capture_chart(g.get("plt"))
        if chart:
            res.update(chart)
            
        return res
