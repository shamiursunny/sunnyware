"""Definitive 112-tool cloud test with 30-min timeout and token tracking."""
import urllib.request
import json
import time

BASE = "https://shamiur-sunnyware.hf.space"
API_KEY = "master-admin-key"
TIMEOUT = 1800  # 30 minutes

LLM_ONLY_TOOLS = {"delegate_to_agent", "execute_plan"}

def _get(path, timeout=30):
    req = urllib.request.Request(f"{BASE}{path}")
    req.add_header("x-api-key", API_KEY)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def _post(path, timeout=1800):
    req = urllib.request.Request(f"{BASE}{path}", method="POST", data=b"{}")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", API_KEY)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def get_analytics_snapshot():
    try:
        ov = _get("/api/analytics/overview")
        llm = _get("/api/llm-dashboard/providers")
        return {"overview": ov, "providers": llm}
    except Exception as e:
        return {"error": str(e)}

def extract_total_tokens(snapshot):
    if not snapshot or "error" in snapshot:
        return 0, 0
    total = 0
    calls = 0
    ov = snapshot.get("overview", {})
    if isinstance(ov, dict):
        for key in ("total_tokens", "tokens_used", "llm_tokens", "llm_calls"):
            v = ov.get(key)
            if isinstance(v, (int, float)):
                if "call" in key:
                    calls += int(v)
                else:
                    total += int(v)
    provs = snapshot.get("providers", {})
    rows = provs.get("providers", []) if isinstance(provs, dict) else []
    for p in rows:
        if isinstance(p, dict):
            for key in ("total_tokens", "tokens", "tokens_used"):
                v = p.get(key)
                if isinstance(v, (int, float)):
                    total += int(v)
            for key in ("calls", "total_calls"):
                v = p.get(key)
                if isinstance(v, (int, float)):
                    calls += int(v)
    return total, calls

def main():
    print("=" * 70)
    print("  DEFINITIVE 112-TOOL CLOUD TEST")
    print(f"  Timeout: {TIMEOUT}s ({TIMEOUT // 60} min) | Endpoint: force mode")
    print("=" * 70)

    print("\n[1/4] Capturing pre-test token snapshot...")
    pre = get_analytics_snapshot()
    pre_tokens, pre_calls = extract_total_tokens(pre)
    print(f"      Pre:  {pre_tokens} tokens, {pre_calls} LLM calls")

    print(f"\n[2/4] Running force test (all 112 tools)...")
    print(f"      This will take 3-10 minutes. Be patient...")
    start = time.time()
    try:
        data = _post("/api/tools-test-all?force=1", timeout=TIMEOUT)
    except Exception as e:
        print(f"      ❌ Test failed: {e}")
        return
    elapsed = time.time() - start
    print(f"      ✅ Complete in {elapsed:.1f}s ({elapsed/60:.1f} min)")

    print("\n[3/4] Capturing post-test token snapshot...")
    post = get_analytics_snapshot()
    post_tokens, post_calls = extract_total_tokens(post)
    delta_tokens = post_tokens - pre_tokens
    delta_calls = post_calls - pre_calls
    print(f"      Post: {post_tokens} tokens, {post_calls} LLM calls")
    print(f"      Delta: +{delta_tokens} tokens, +{delta_calls} LLM calls")

    print("\n[4/4] Analyzing results...")
    s = data.get("summary", {})
    results = data.get("results", [])

    zt_pass, zt_fail, zt_skip = [], [], []
    llm_pass, llm_fail, llm_skip = [], [], []

    for r in results:
        name = r["name"]
        status = r["status"]
        if name in LLM_ONLY_TOOLS:
            (llm_pass if status == "PASS" else
             llm_fail if status == "FAIL" else llm_skip).append(r)
        else:
            (zt_pass if status == "PASS" else
             zt_fail if status == "FAIL" else zt_skip).append(r)

    print("\n" + "=" * 70)
    print("  FINAL REPORT")
    print("=" * 70)
    print(f"\n  Total time:  {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Total tools: {s.get('total')}")
    print(f"  Passed:      {s.get('passed')}")
    print(f"  Failed:      {s.get('failed')}")
    print(f"  Skipped:     {s.get('skipped')}")

    print(f"\n  ── ZERO-TOKEN ROUTED (110 tools) ──")
    print(f"     PASS:  {len(zt_pass)}")
    print(f"     FAIL:  {len(zt_fail)}")
    print(f"     SKIP:  {len(zt_skip)}")

    print(f"\n  ── LLM-REQUIRED (2 tools) ──")
    print(f"     PASS:  {len(llm_pass)}")
    print(f"     FAIL:  {len(llm_fail)}")
    print(f"     SKIP:  {len(llm_skip)}")

    print(f"\n  ── TOKEN COST (delta during test) ──")
    print(f"     Tokens: {delta_tokens}")
    print(f"     LLM calls: {delta_calls}")
    if delta_calls > 0:
        print(f"     Avg per call: {delta_tokens // delta_calls} tokens")

    if zt_fail:
        print(f"\n  ── ZERO-TOKEN FAILURES ({len(zt_fail)}) ──")
        for r in zt_fail:
            print(f"     {r['name']}: {r['error'][:100]}")

    if llm_fail:
        print(f"\n  ── LLM-TOOL FAILURES ({len(llm_fail)}) ──")
        for r in llm_fail:
            print(f"     {r['name']}: {r['error'][:100]}")

    print(f"\n  ── LLM-REQUIRED TOOL DETAILS ──")
    for r in llm_pass + llm_fail + llm_skip:
        print(f"     {r['name']:25} {r['status']:6} ({r['latency_ms']}ms)")

    print("\n" + "=" * 70)
    print("  TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
