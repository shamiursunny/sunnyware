import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path("src").absolute()))

from sunnyware.tools import _TOOLS
from sunnyware.needle_tool_loader import build_schema_from_tool
from sunnyware import local_llm

async def main():
    print(f"[1] Building schemas for {len(_TOOLS)} tools...")
    all_schemas = [build_schema_from_tool(tool) for tool in _TOOLS.values()]
    print(f"[2] Built {len(all_schemas)} schemas.")

    prompt = "Use Python to calculate the first 10 fibonacci numbers."
    system = "You are a helpful assistant."

    print("[3] Calling local LLM (this may take a few minutes)...")
    res = await local_llm.chat(
        prompt=prompt,
        system=system,
        history=[],
        tools=all_schemas,
        timeout=300.0
    )

    print("\n=== FINAL RESULT ===")
    print(f"ok: {res.get('ok')}")
    print(f"error: {res.get('error')}")
    
    content = res.get('content')
    if content:
        print(f"content (first 500 chars): {content[:500]}")
    else:
        print("content: None")
        
    tool_calls = res.get('tool_calls')
    print(f"tool_calls: {tool_calls}")

if __name__ == "__main__":
    asyncio.run(main())
