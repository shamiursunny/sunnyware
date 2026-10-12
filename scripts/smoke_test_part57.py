#!/usr/bin/env python3
"""Part 57 smoke test — streaming fallback + live provider tracking."""
import ast, sys, asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

PASS, FAIL = 0, 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def main():
    print("=" * 62)
    print(" Part 57 — streaming provider fallback")
    print("=" * 62)

    llm_file = ROOT / "src/sunnyware/llm.py"
    agent_file = ROOT / "src/sunnyware/routes/agent.py"

    llm_src = llm_file.read_text(encoding="utf-8")
    agent_src = agent_file.read_text(encoding="utf-8")

    print("\n  llm.py:")
    check("_LAST_STREAM_PROVIDER global",
          "_LAST_STREAM_PROVIDER" in llm_src)
    check("get_last_stream_provider() defined",
          "def get_last_stream_provider" in llm_src)
    check("stream_chat iterates providers",
          "for p in provs:" in llm_src)
    check("cooling providers skipped",
          "p.is_cooling()" in llm_src)
    check("429 triggers cooldown",
          "p.mark_cooldown(60.0)" in llm_src)
    check("yielded_any guard for mid-stream",
          "yielded_any" in llm_src)
    check("raises if all providers fail",
          "all providers failed" in llm_src)

    print("\n  agent.py:")
    check("start event no longer pre-reads provider",
          "from ..providers import load_providers as _lp" not in agent_src
          or "yield f\"data: {_json.dumps({'type': 'start'" in agent_src)
    check("done event queries live provider",
          "get_last_stream_provider" in agent_src)

    print("\n  syntax:")
    for f in (llm_file, agent_file):
        try:
            ast.parse(f.read_text(encoding="utf-8"))
            check(f"{f.name} parses", True)
        except SyntaxError as e:
            check(f"{f.name} parses", False, detail=str(e))

    print("\n  integration (local stream):")
    try:
        from sunnyware import llm
        async def run_stream():
            chunks = []
            async for c in llm.stream_chat("Say exactly the word PONG."):
                chunks.append(c)
                if sum(len(x) for x in chunks) > 30:
                    break
            return "".join(chunks), llm.get_last_stream_provider()
        text, provider = asyncio.run(run_stream())
        check("stream produced output", bool(text.strip()), detail=repr(text[:80]))
        check("provider was recorded", provider is not None,
              detail=f"got {provider!r}")
        # Legacy single-provider mode reports name="default" when
        # LLM_PROVIDERS is unset. On HF it's groq/gemini/openrouter.
        check(f"provider is a non-empty string ({provider!r})",
              isinstance(provider, str) and len(provider) > 0)
    except Exception as e:
        check("integration stream", False, detail=f"{type(e).__name__}: {e}")

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
