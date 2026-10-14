# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 100 smoke test - auto-learn provider prompt limits."""
from pathlib import Path
import ast, sys, os, tempfile, json

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 100: auto-learn provider prompt limits ===")

# 1. Module exists
pl_path = SRC / "provider_limits.py"
check("provider_limits.py exists", pl_path.is_file())
pl_src = pl_path.read_text(encoding="utf-8") if pl_path.is_file() else ""
try:
    ast.parse(pl_src)
    check("provider_limits.py parses", True)
except SyntaxError as e:
    check("provider_limits.py parses", False, str(e))

# 2. Module API
check("load_learned() defined", "def load_learned(" in pl_src)
check("get_learned() defined", "def get_learned(" in pl_src)
check("learn_limit() defined", "def learn_limit(" in pl_src)
check("reset() defined", "def reset(" in pl_src)
check("snapshot() defined", "def snapshot(" in pl_src)
check("_LEARN_MARGIN used", "_LEARN_MARGIN" in pl_src)
check("_LEARN_MIN used", "_LEARN_MIN" in pl_src)
check("HF Space /data detection", "SPACE_ID" in pl_src and "/data" in pl_src)

# 3. Providers integration
prov = (SRC / "providers.py").read_text(encoding="utf-8")
check("providers.py imports learned limits",
      "from . import provider_limits as _pl" in prov)
check("providers.py applies learned (Part 100 comment)",
      "Part 100: learned limit beats hardcoded default" in prov)
check("env override still wins (skips learned when env set)",
      "else:" in prov and "learned" in prov)

# 4. llm.py integration
llm = (SRC / "llm.py").read_text(encoding="utf-8")
check("_is_too_large_error() defined", "def _is_too_large_error(" in llm)
check("detects 413", '"413" in e' in llm)
check("detects 'request too large'", "request too large" in llm)
check("learn call in loop", "provider_limit_learned" in llm)
check("learn_limit called with prompt tokens",
      "_pl.learn_limit(p.name, _prompt_tokens" in llm)
check("short cooldown after learning",
      "p.mark_cooldown(60.0)" in llm)

# 5. Live behavior — set a temp data dir, learn, persist, reload
sys.path.insert(0, str(SRC.parent))
tmp = tempfile.mkdtemp(prefix="pl_test_")
os.environ["SUNNYWARE_DATA_DIR"] = tmp
try:
    # Force fresh module load
    for mod in list(sys.modules):
        if mod.startswith("sunnyware.provider_limits"):
            del sys.modules[mod]
    from sunnyware import provider_limits as pl

    # Test 1: learn_limit returns new lower value
    new_limit = pl.learn_limit("groq", 9000, 0)
    check("learn_limit(9000) -> 8800", new_limit == 8800, f"got {new_limit}")

    # Test 2: never raises existing lower limit
    again = pl.learn_limit("groq", 20000, 8000)
    check("learn_limit never raises existing lower", again == 8000, f"got {again}")

    # Test 3: clamps to _LEARN_MIN
    tiny = pl.learn_limit("tiny_provider", 100, 0)
    check("clamps to _LEARN_MIN (500)", tiny == 500, f"got {tiny}")

    # Test 4: persistence to disk
    learned_file = Path(tmp) / "provider_limits.json"
    check("persisted to disk", learned_file.is_file())
    if learned_file.is_file():
        data = json.loads(learned_file.read_text(encoding="utf-8"))
        check("JSON has groq=8800", data.get("groq") == 8800, str(data))

    # Test 5: reset clears
    pl.reset("groq")
    check("reset clears entry", pl.get_learned("groq") is None)

    # Test 6: snapshot returns dict
    snap = pl.snapshot()
    check("snapshot returns dict", isinstance(snap, dict))
    check("snapshot still has tiny_provider",
          snap.get("tiny_provider") == 500)
except Exception as e:
    check("live module test", False, f"{type(e).__name__}: {e}")
finally:
    try:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    os.environ.pop("SUNNYWARE_DATA_DIR", None)

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    print("\nFAILED CHECKS:")
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
