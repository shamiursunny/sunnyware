#!/usr/bin/env python3
"""Part 56 smoke test — api_call tool."""
import ast, os, sys, asyncio
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
    print(" Part 56 — api_call tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/api_call.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("api_call.py exists", tool_file.exists())
    if not tool_file.exists():
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class ApiCallTool" in src)
    check("name = api_call", 'name = "api_call"' in src)
    check("SSRF guard present", "_is_private_host" in src)
    check("allowlist support", "_allowlist" in src)
    check("method allowlist", "_ALLOWED_METHODS" in src)
    check("response size cap", "_MAX_RESPONSE_BYTES" in src)
    check("registered in __init__",
          "ApiCallTool.name: ApiCallTool()" in init_src)

    try:
        ast.parse(src)
        check("api_call.py parses", True)
    except SyntaxError as e:
        check("api_call.py parses", False, detail=str(e))

    try:
        import httpx  # noqa
        check("httpx importable", True)
    except Exception as e:
        check("httpx importable", False, detail=str(e))
        return 1 if FAIL else 0

    # ── Unit tests on helpers ────────────────────────────────
    from sunnyware.tools.api_call import _is_private_host, _check_url

    check("localhost blocked", _is_private_host("localhost"))
    check("127.0.0.1 blocked", _is_private_host("127.0.0.1"))
    check("::1 blocked", _is_private_host("::1"))
    check("10.0.0.1 blocked", _is_private_host("10.0.0.1"))
    check("192.168.1.1 blocked", _is_private_host("192.168.1.1"))
    check("169.254.1.1 blocked", _is_private_host("169.254.1.1"))
    check("8.8.8.8 allowed", not _is_private_host("8.8.8.8"))

    check("ftp:// rejected", _check_url("ftp://example.com") is not None)
    check("javascript: rejected", _check_url("javascript:alert(1)") is not None)
    check("no scheme rejected", _check_url("example.com") is not None)
    check("empty rejected", _check_url("") is not None)
    check("https://example.com allowed", _check_url("https://example.com") is None)
    check("http://localhost blocked", _check_url("http://localhost:8080/x") is not None)
    check("http://10.0.0.5/x blocked", _check_url("http://10.0.0.5/x") is not None)

    # Allowlist behavior
    os.environ["SUNNYWARE_API_ALLOWLIST"] = "example.com,api.github.com"
    check("allowlist permits example.com",
          _check_url("https://example.com/x") is None)
    check("allowlist permits subdomain",
          _check_url("https://api.example.com/x") is None)
    check("allowlist blocks evil.com",
          _check_url("https://evil.com/x") is not None)
    del os.environ["SUNNYWARE_API_ALLOWLIST"]

    # ── Live HTTP (soft — skip if offline) ───────────────────
    async def run(**kw):
        from sunnyware.tools.api_call import ApiCallTool
        return await ApiCallTool().run(kw)

    check("no url rejected", "error" in asyncio.run(run()))
    check("bad method rejected",
          "error" in asyncio.run(run(url="https://example.com", method="FROB")))
    check("bad headers rejected",
          "error" in asyncio.run(run(url="https://example.com", headers="x")))

    try:
        r = asyncio.run(run(url="https://httpbin.org/json", timeout=10))
        if "error" in r:
            print(f"  [SKIP] live http: {r['error'][:80]}")
        else:
            check("live GET httpbin.org/json returns 200", r.get("status_code") == 200)
            check("live GET parsed JSON body", "json" in r)
            check("live response has content_type", bool(r.get("content_type")))
    except Exception as e:
        print(f"  [SKIP] live http: {type(e).__name__}: {e}")

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
