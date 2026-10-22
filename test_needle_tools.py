# test_needle_tools.py
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def run_tool_test():
    """Test all 83 tools individually and return results."""
    from sunnyware.tools import _TOOLS
    from sunnyware.needle_tool_loader import build_schema_from_tool
    from sunnyware.needle_router import try_needle_route
    
    results = []
    for name, tool in _TOOLS.items():
        try:
            schema = build_schema_from_tool(tool)
            prompt = f"Please use the {name} tool to help me."
            result = await try_needle_route(prompt, [schema])
            
            if result and result.get("tool") == name:
                results.append({"tool": name, "status": "PASS", "args": result.get("args")})
                print(f"[PASS] {name}", flush=True)
            else:
                results.append({"tool": name, "status": "FAIL", "response": str(result)})
                print(f"[FAIL] {name} -> {result}", flush=True)
        except Exception as e:
            results.append({"tool": name, "status": "ERROR", "error": str(e)})
            print(f"[ERROR] {name} -> {e}", flush=True)
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "results": results
    }
    print(f"\nSUMMARY: {passed}/{len(results)} passed", flush=True)
    return summary
