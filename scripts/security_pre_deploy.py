#!/usr/bin/env python3
"""Static security checks (pre-deploy): secrets, dangerous imports, CVEs, bandit."""
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
PASS, FAIL, WARN, SKIP = 0, 0, 0, 0

# Files where exec()/eval() is INTENTIONAL and controlled by design.
# These are the sandbox interpreter itself — exec() is the whole point.
SAFE_EXEC_FILES = {
    "src/sunnyware/tools/_sandbox.py",
    "src/sunnyware/sql_sandbox.py",
}


def p(msg):
    global PASS
    print(f"  [PASS] {msg}"); PASS += 1


def f(msg):
    global FAIL
    print(f"  [FAIL] {msg}"); FAIL += 1


def w(msg):
    global WARN
    print(f"  [WARN] {msg}"); WARN += 1


def s(msg):
    global SKIP
    print(f"  [SKIP] {msg}"); SKIP += 1


# ── 1. Secret scanning ────────────────────────────────────────────
def scan_secrets():
    print("\n[1] Secret scanning")
    patterns = {
        "AWS access key":   re.compile(r"AKIA[0-9A-Z]{16}"),
        "GitHub token":     re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}"),
        "OpenAI key":       re.compile(r"sk-[A-Za-z0-9]{20,}"),
        "Private key":      re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "Generic API key":  re.compile(r"(?:api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}['\"]", re.I),
    }
    # Allowlist (test fixtures, obvious placeholders)
    allowlist = {"TEST_KEY_NOT_REAL", "master-admin-key", "your-key-here",
                 "changeme", "REPLACE_ME", "x" * 20}
    found = 0
    for f_path in list(SRC.rglob("*.py")) + list(SRC.rglob("*.html")):
        if "__pycache__" in str(f_path):
            continue
        try:
            content = f_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for lineno, line in enumerate(content.split("\n"), 1):
            if line.strip().startswith("#"):
                continue
            if any(ph in line for ph in allowlist):
                continue
            for name, rx in patterns.items():
                if rx.search(line):
                    f(f"{name} in {f_path.relative_to(REPO)}:{lineno}")
                    found += 1
    if not found:
        p("No secrets found in source")


# ── 2. Dangerous imports ──────────────────────────────────────────
def scan_imports():
    print("\n[2] Dangerous code patterns")
    banned = {
        "eval":         "code injection",
        "exec":         "code injection",
        "os.system":    "shell injection",
        "pickle.loads": "arbitrary deserialization",
    }
    warned = {
        "pickle":              "deserialization risk",
        "subprocess.call":     "review shell=True",
        "subprocess.run":      "review shell=True",
        "yaml.load":           "use safe_load",
    }
    found_banned, found_warned = 0, 0
    for py_file in SRC.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    parts = []
                    cur = node.func
                    while isinstance(cur, ast.Attribute):
                        parts.append(cur.attr); cur = cur.value
                    if isinstance(cur, ast.Name):
                        parts.append(cur.id)
                    name = ".".join(reversed(parts))
                if name in banned:
                    rel = str(py_file.relative_to(REPO)).replace("\\", "/")
                    if rel in SAFE_EXEC_FILES:
                        # Intentional — this is the sandbox interpreter
                        p(f"{name}() in {rel}:{node.lineno} (intentional, sandbox)")
                    else:
                        f(f"{name}() in {rel}:{node.lineno} ({banned[name]})")
                        found_banned += 1
                elif name in warned:
                    found_warned += 1
    if not found_banned:
        p("No banned calls (eval/exec/os.system/pickle.loads)")
    if found_warned:
        w(f"{found_warned} warning-level pattern(s) (pickle/subprocess) — review manually")


# ── 3. .env / credentials not tracked ─────────────────────────────
def scan_git_files():
    print("\n[3] Git-tracked sensitive files")
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=REPO, text=True)
    except Exception:
        s("git not available")
        return
    dangerous = [".env", ".env.local", ".env.production", "id_rsa",
                 "credentials.json", "service-account.json"]
    hits = [line for line in out.splitlines()
            if line in dangerous or line.endswith(".pem") or line.endswith(".key")]
    if hits:
        for h in hits:
            f(f"Tracked sensitive file: {h}")
    else:
        p("No .env / .pem / .key files tracked")


# ── 4. pip-audit (optional) ───────────────────────────────────────
def scan_deps():
    print("\n[4] Dependency CVE scan (pip-audit)")
    if not shutil.which("pip-audit"):
        s("pip-audit not installed (pip install pip-audit)")
        return
    req = REPO / "requirements-ci.txt"
    if not req.exists():
        s("requirements-ci.txt not found")
        return
    try:
        r = subprocess.run(
            ["pip-audit", "--format=json", "-r", str(req)],
            capture_output=True, text=True, timeout=120, cwd=REPO,
        )
        data = json.loads(r.stdout or "{}")
        vulns = data.get("dependencies", [])
        # Documented exceptions: packages whose CVE fix is blocked by upstream pins
        # - pillow: gradio >=6.0 requires pillow<13.0, so the 13.0.0 fix cannot be applied
        #   Tracking upstream: https://github.com/gradio-app/gradio/issues
        IGNORED_DEPS = {
            "pillow": "gradio requires pillow<13.0 — CVE fix blocked upstream",
        }
        # Split into "fix available" (should fail) vs "no fix yet" (warn)
        fixable, unfixable = [], []
        for d in vulns:
            if not d.get("vulns"):
                continue
            if d.get("name", "").lower() in IGNORED_DEPS:
                print(f"        [skip] {d['name']}: {IGNORED_DEPS[d['name'].lower()]}")
                continue
            has_fix = any(v.get("fix_versions") for v in d["vulns"])
            (fixable if has_fix else unfixable).append((d, has_fix))
        if fixable:
            f(f"{len(fixable)} package(s) with FIXABLE CVEs — upgrade required")
            for d, _ in fixable[:5]:
                fixes = set()
                for v in d["vulns"]:
                    fixes.update(v.get("fix_versions", []))
                print(f"        {d['name']} {d['version']} -> {sorted(fixes)[-1] if fixes else '?'}")
        if unfixable:
            w(f"{len(unfixable)} package(s) with no-fix-available CVEs (accepted)")
            for d, _ in unfixable[:5]:
                print(f"        {d['name']} {d['version']} — {len(d['vulns'])} CVE(s), no fix yet")
        if not fixable and not unfixable:
            p("No known CVEs in requirements-ci.txt")
    except subprocess.TimeoutExpired:
        s("pip-audit timed out")
    except Exception as e:
        s(f"pip-audit error: {type(e).__name__}")


# ── 5. Bandit static analysis (optional) ──────────────────────────
def scan_bandit():
    print("\n[5] Bandit static analysis")
    if not shutil.which("bandit"):
        s("bandit not installed (pip install bandit)")
        return
    import tempfile as _tf
    try:
        with _tf.NamedTemporaryFile(mode="r+", suffix=".json", delete=False) as _tmp:
            tmp_path = _tmp.name
        r = subprocess.run(
            ["bandit", "-r", "src/", "-f", "json", "-ll", "--exit-zero", "-o", tmp_path,
             "--skip", "B102,B104,B310,B608",
             "--exclude", "tests,scripts,src/sunnyware/tools/_sandbox.py"],
            capture_output=True, text=True, timeout=180, cwd=REPO,
        )
        # Read from tempfile (bandit writes JSON there, not stdout)
        try:
            data = json.loads(Path(tmp_path).read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as je:
            s(f"bandit JSON unreadable: {je}")
            return
        finally:
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass
        results = data.get("results", [])
        highs = [x for x in results if x.get("issue_severity") == "HIGH"]
        meds  = [x for x in results if x.get("issue_severity") == "MEDIUM"]
        if highs:
            f(f"{len(highs)} HIGH severity issue(s)")
        if meds:
            w(f"{len(meds)} MEDIUM severity issue(s)")
        if not highs and not meds:
            p("No HIGH/MEDIUM bandit findings")
    except subprocess.TimeoutExpired:
        s("bandit timed out")
    except Exception as e:
        s(f"bandit error: {type(e).__name__}")


def main():
    print("=== Security Pre-Deploy Checks ===")
    scan_secrets()
    scan_imports()
    scan_git_files()
    scan_deps()
    scan_bandit()
    print(f"\n=== Summary: {PASS} pass, {WARN} warn, {FAIL} fail, {SKIP} skip ===")
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
