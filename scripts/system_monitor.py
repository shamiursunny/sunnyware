#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Sunnyware System Monitor - comprehensive health, verification, and
roadmap tracking.

Runs 40+ checks across 9 categories. Reports current state + score +
actionable recommendations. Understandable by any human or AI.

Usage:
    python scripts/system_monitor.py              # full run
    python scripts/system_monitor.py --quick      # skip network, skip slow
    python scripts/system_monitor.py --offline    # no network at all
    python scripts/system_monitor.py --json       # JSON only
    python scripts/system_monitor.py --watch 300  # loop every 5 min
    python scripts/system_monitor.py --baseline   # save as baseline
    python scripts/system_monitor.py --diff       # compare to baseline

Exit codes:
    0 = all checks passed
    1 = warnings only
    2 = at least one FAIL
"""

import argparse
import ast
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# -- Project root -----------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports"
BASELINE_PATH = SCRIPTS / "system_baseline.json"


# -- Expected state (the "spec" of the codebase) ----------------------------
REQUIRED_DIRS = [
    "src/sunnyware",
    "src/sunnyware/rag",
    "src/sunnyware/tools",
    "src/sunnyware/routes",
    "scripts",
    "config",
]

REQUIRED_FILES = [
    "src/sunnyware/main.py",
    "src/sunnyware/orchestrator.py",
    "src/sunnyware/llm.py",
    "src/sunnyware/providers.py",
    "src/sunnyware/model_resolver.py",
    "src/sunnyware/webui.py",
    "src/sunnyware/prompts.py",
    "src/sunnyware/memory.py",
    "src/sunnyware/paths.py",
    "src/sunnyware/routes/rag.py",
    "src/sunnyware/routes/sessions.py",
    "src/sunnyware/routes/meta.py",
    "src/sunnyware/rag/embeddings.py",
    "src/sunnyware/rag/chunker.py",
    "src/sunnyware/rag/extractor.py",
    "src/sunnyware/rag/vector_store.py",
    "src/sunnyware/rag/report_generator.py",
    "requirements.txt",
    "README.md",
    "WORKFLOW.md",
    "HANDOFF.md",
    "AGENTS.md",
    "RESUME.md",
    ".gitignore",
]

EXPECTED_TOOLS = frozenset([
    "echo", "current_time", "read_file", "write_file", "calculator",
    "web_fetch", "memory_search", "web_search", "weather", "date_calc",
    "python_eval", "list_files", "delete_file", "mkdir",
    "rag_search", "rag_list",
])

KEY_MODULES = [
    "sunnyware.main",
    "sunnyware.orchestrator",
    "sunnyware.llm",
    "sunnyware.providers",
    "sunnyware.model_resolver",
    "sunnyware.webui",
    "sunnyware.rag",
    "sunnyware.tools",
    "sunnyware.routes.rag",
    "sunnyware.routes.sessions",
    "sunnyware.routes.meta",
]

WEBUI_REQUIRED_MARKERS = [
    'id="chat"',
    'id="sidebar"',
    'id="newChatBtn"',
    'id="exportBtn"',
    'id="importBtn"',
    'id="usageBtn"',
    'id="usageModal"',
    "async function sendMessage",
    "async function openUsageModal",
    "function exportSessions",
    "function importSessions",
    "async function loadSessionWithFallback",
    "async function hydrateFromNeon",
]

SUPPORTED_EXTENSIONS = frozenset([
    ".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls",
])

REQUIRED_ROUTES = {
    "src/sunnyware/routes/rag.py": [
        '"/api/rag/status"',
        '"/api/rag/upload"',
        '"/api/rag/query"',
        '"/api/rag/reset"',
    ],
    "src/sunnyware/routes/sessions.py": [
        '"/api/sessions"',
        "/history",
    ],
    "src/sunnyware/routes/meta.py": [
        '"/health/live"',
        '"/health/ready"',
        '"/api/providers/status"',
        '"/api/models/resolve"',
    ],
    "src/sunnyware/routes/agent.py": [
        '"/api/agent/run"',
        '"/api/agent/run/stream"',
    ],
}

# Known accepted limitations - shown in report but do NOT affect score
KNOWN_LIMITATIONS = [
    "Mistral free tier IP-throttled from Bangladesh (removed from LLM_PROVIDERS)",
    "Local GGUF (MiniCPM5-2B) not viable on HF 2 vCPU (502 timeout at 8 min)",
    "NVIDIA NIM pending account verification",
    "polars removed (requires AVX2/FMA - crashes on 3rd-gen i7)",
    "JS escape bug: Python triple-quote needs doubled backslashes for JS strings",
    "localStorage wipe requires Ctrl+Shift+R (not Ctrl+Shift+Delete with cookies)",
]

# Pending features roadmap - tracked here for visibility
PENDING_FEATURES = [
    {"id": "nvidia-nim", "title": "NVIDIA NIM integration",
     "blocker": "awaiting support verification email reply"},
    {"id": "voice-input", "title": "Voice input (browser mic -> text)",
     "effort": "~30 min", "priority": "low"},
    {"id": "markdown-render", "title": "Full markdown rendering in chat",
     "effort": "~20 min", "priority": "medium"},
    {"id": "session-rename", "title": "Session rename inline edit",
     "effort": "~25 min", "priority": "low"},
    {"id": "part-41", "title": "Part 41 - define next milestone",
     "blocker": "pending decision"},
]


# -- Check framework --------------------------------------------------------

class CheckResult:
    def __init__(self, category, name, status, message="", detail=None,
                 severity="medium"):
        self.category = category
        self.name = name
        self.status = status  # PASS / WARN / FAIL / SKIP
        self.message = message
        self.detail = detail or {}
        self.severity = severity  # critical / high / medium / low

    def to_dict(self):
        return {
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "severity": self.severity,
            "detail": self.detail,
        }


SEVERITY_WEIGHTS = {
    "critical": 10,
    "high": 5,
    "medium": 3,
    "low": 1,
}


class Monitor:
    def __init__(self, offline=False, quick=False, verbose=False):
        self.offline = offline
        self.quick = quick
        self.verbose = verbose
        self.results = []
        self.t_start = time.time()

    def add(self, category, name, ok, message="", detail=None,
            severity="medium"):
        """ok: True=PASS, False=FAIL, None=WARN, 'skip'=SKIP"""
        if ok is True:
            status = "PASS"
        elif ok is False:
            status = "FAIL"
        elif ok is None:
            status = "WARN"
        else:
            status = "SKIP"
        self.results.append(CheckResult(category, name, status, message,
                                        detail, severity))

    def run_checks(self):
        self.check_environment()
        self.check_structure()
        self.check_syntax()
        self.check_imports()
        self.check_tools()
        self.check_providers()
        self.check_model_resolver()
        self.check_rag()
        self.check_webui()
        self.check_routes()
        self.check_docs()
        self.check_prepush()
        self.check_git()
        self.check_security()
        self.check_hygiene()
        if not self.offline and not self.quick:
            self.check_network()

    # -- Category 1: environment --------------------------------------------
    def check_environment(self):
        cat = "environment"
        # Python version
        v = sys.version_info
        self.add(cat, "Python version >= 3.10",
                 v.major == 3 and v.minor >= 10,
                 f"found {v.major}.{v.minor}.{v.micro}",
                 severity="critical")

        # venv active
        in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
        self.add(cat, "Virtual environment active",
                 in_venv, f"sys.prefix = {sys.prefix}",
                 severity="low")

        # CWD is project root
        cwd_ok = Path.cwd() == ROOT or (ROOT / ".git").exists()
        self.add(cat, "Running from project root",
                 cwd_ok, f"cwd = {Path.cwd()}",
                 severity="low")

    # -- Category 2: structure ----------------------------------------------
    def check_structure(self):
        cat = "structure"
        missing_dirs = [d for d in REQUIRED_DIRS if not (ROOT / d).is_dir()]
        self.add(cat, "Required directories present",
                 len(missing_dirs) == 0,
                 f"{len(REQUIRED_DIRS) - len(missing_dirs)}/"
                 f"{len(REQUIRED_DIRS)} found",
                 detail={"missing": missing_dirs},
                 severity="high")

        missing_files = [f for f in REQUIRED_FILES if not (ROOT / f).is_file()]
        self.add(cat, "Required files present",
                 len(missing_files) == 0,
                 f"{len(REQUIRED_FILES) - len(missing_files)}/"
                 f"{len(REQUIRED_FILES)} found",
                 detail={"missing": missing_files},
                 severity="high")

        # .gitignore coverage
        gi = ROOT / ".gitignore"
        if gi.exists():
            content = gi.read_text(encoding="utf-8", errors="ignore")
            checks = {
                ".env": ".env" in content,
                "data/": "data/" in content,
                "__pycache__": "__pycache__" in content,
                "*.bak.*": "*.bak" in content,
            }
            missing = [k for k, v in checks.items() if not v]
            self.add(cat, ".gitignore covers key patterns",
                     len(missing) == 0,
                     f"{len(checks) - len(missing)}/{len(checks)} matched",
                     detail={"missing_patterns": missing},
                     severity="low")

    # -- Category 3: syntax -------------------------------------------------
    def check_syntax(self):
        cat = "syntax"
        for base in [SRC, SCRIPTS]:
            if not base.exists():
                continue
            files = sorted(base.rglob("*.py"))
            bad = []
            for f in files:
                try:
                    ast.parse(f.read_text(encoding="utf-8"))
                except SyntaxError as e:
                    bad.append(f"{f.relative_to(ROOT)}: line {e.lineno}")
            self.add(cat, f"Python syntax: {base.name}",
                     len(bad) == 0,
                     f"{len(files)} files, {len(bad)} errors",
                     detail={"errors": bad[:10]},
                     severity="critical")

    # -- Category 4: imports ------------------------------------------------
    def check_imports(self):
        cat = "imports"
        sys.path.insert(0, str(SRC))
        # Silence logs during imports
        import logging
        logging.disable(logging.CRITICAL)
        for mod in KEY_MODULES:
            try:
                __import__(mod)
                self.add(cat, f"Import {mod}", True, "ok",
                         severity="high")
            except Exception as e:
                self.add(cat, f"Import {mod}", False,
                         f"{type(e).__name__}: {e}",
                         severity="high")
        logging.disable(logging.NOTSET)

    # -- Category 5: tools --------------------------------------------------
    def check_tools(self):
        cat = "tools"
        try:
            from sunnyware import tools as tools_registry
            names = set(tools_registry.tool_names())
            missing = EXPECTED_TOOLS - names
            extra = names - EXPECTED_TOOLS
            self.add(cat, "Tools registry has all 16 expected tools",
                     len(missing) == 0,
                     f"{len(names)} registered",
                     detail={"missing": sorted(missing),
                             "extra": sorted(extra)},
                     severity="high")
            # Each tool has required fields
            bad_tools = []
            for n in names:
                t = tools_registry.get_tool(n)
                if not getattr(t, "name", None):
                    bad_tools.append(f"{n}: no name attr")
                if not getattr(t, "description", None):
                    bad_tools.append(f"{n}: no description")
                if getattr(t, "parameters", None) is None:
                    bad_tools.append(f"{n}: no parameters")
            self.add(cat, "All tools have name/description/parameters",
                     len(bad_tools) == 0,
                     f"{len(names) - len(bad_tools)}/{len(names)} valid",
                     detail={"invalid": bad_tools[:5]},
                     severity="medium")
        except Exception as e:
            self.add(cat, "Tools registry loadable", False,
                     f"{type(e).__name__}: {e}", severity="critical")

    # -- Category 6: providers ----------------------------------------------
    def check_providers(self):
        cat = "providers"
        try:
            from sunnyware import providers as _p
            _p.reset_for_tests()
            provs = _p.load_providers()
            self.add(cat, "Providers load successfully",
                     len(provs) > 0,
                     f"{len(provs)} providers configured",
                     detail={"names": [p.name for p in provs]},
                     severity="critical")
            # Each provider has required fields
            bad = [p.name for p in provs
                   if not (p.name and p.base_url and p.model)]
            self.add(cat, "All providers have name/url/model",
                     len(bad) == 0,
                     f"{len(provs) - len(bad)}/{len(provs)} valid",
                     detail={"invalid": bad},
                     severity="high")
            # Provider type is set
            bad_type = [p.name for p in provs
                        if p.provider_type not in ("http", "local")]
            self.add(cat, "All providers have valid type",
                     len(bad_type) == 0,
                     "types valid",
                     detail={"invalid": bad_type},
                     severity="medium")
        except Exception as e:
            self.add(cat, "Providers module loadable", False,
                     f"{type(e).__name__}: {e}", severity="critical")

    # -- Category 7: model resolver -----------------------------------------
    def check_model_resolver(self):
        cat = "model-resolver"
        try:
            from sunnyware import model_resolver as mr
            prefs = getattr(mr, "PREFERENCES", {})
            expected = {"mistral", "gemini", "openrouter", "groq", "nvidia"}
            missing = expected - set(prefs.keys())
            self.add(cat, "Preference lists for all 5 providers",
                     len(missing) == 0,
                     f"{len(prefs)} lists present",
                     detail={"missing": sorted(missing)},
                     severity="medium")
            # Each list has at least 3 fallbacks
            short = [k for k, v in prefs.items() if len(v) < 3]
            self.add(cat, "Each preference list has >= 3 fallbacks",
                     len(short) == 0,
                     f"{len(prefs) - len(short)}/{len(prefs)} sufficient",
                     detail={"short_lists": short},
                     severity="low")
        except Exception as e:
            self.add(cat, "Model resolver loadable", False,
                     f"{type(e).__name__}: {e}", severity="high")

    # -- Category 8: RAG ----------------------------------------------------
    def check_rag(self):
        cat = "rag"
        try:
            from sunnyware.rag import embeddings, extractor, chunker
            # embeddings
            dim = embeddings.dim()
            mid = embeddings.model_id()
            self.add(cat, "Embeddings dim == 384",
                     dim == 384, f"dim={dim}",
                     severity="high")
            self.add(cat, "Embedding model id set",
                     bool(mid), f"model={mid}",
                     severity="medium")
            # extractor
            exts = set(extractor.supported_extensions())
            missing = SUPPORTED_EXTENSIONS - exts
            self.add(cat, "Extractor supports all 7 formats",
                     len(missing) == 0,
                     f"{len(exts)} formats",
                     detail={"missing": sorted(missing)},
                     severity="medium")
            # chunker
            test_chunks = chunker.chunk_text("hello world " * 500, "test.txt")
            self.add(cat, "Chunker produces chunks",
                     len(test_chunks) > 0,
                     f"{len(test_chunks)} chunks for test input",
                     severity="medium")
            # vector store
            from sunnyware.rag import vector_store
            self.add(cat, "Vector store class exists",
                     hasattr(vector_store, "FPAVectorStore"),
                     "FPAVectorStore found",
                     severity="high")
        except Exception as e:
            self.add(cat, "RAG package loadable", False,
                     f"{type(e).__name__}: {e}", severity="critical")


    # -- Category 9: WebUI --------------------------------------------------
    def check_webui(self):
        cat = "webui"
        try:
            from sunnyware import webui
            html = webui.HTML
            # Runtime markers
            missing = [m for m in WEBUI_REQUIRED_MARKERS if m not in html]
            self.add(cat, "WebUI has all required DOM/JS markers",
                     len(missing) == 0,
                     f"{len(WEBUI_REQUIRED_MARKERS) - len(missing)}/"
                     f"{len(WEBUI_REQUIRED_MARKERS)} present",
                     detail={"missing": missing},
                     severity="high")
            # Served HTML size
            html_len = len(html)
            self.add(cat, "Served HTML size reasonable",
                     html_len > 20000,
                     f"{html_len} chars",
                     severity="low")
            # Escape-bug detector: no raw newline inside single-quoted JS strings
            lines = html.splitlines()
            potential_bugs = []
            for i, ln in enumerate(lines):
                stripped = ln.rstrip()
                if stripped.count("'") % 2 == 1 and "//" not in stripped[-30:]:
                    potential_bugs.append(i + 1)
            self.add(cat, "No obvious broken JS string literals",
                     len(potential_bugs) == 0,
                     f"{len(potential_bugs)} potential breaks",
                     detail={"lines": potential_bugs[:5]},
                     severity="critical")
        except Exception as e:
            self.add(cat, "WebUI module loadable", False,
                     f"{type(e).__name__}: {e}", severity="critical")

    # -- Category 10: routes ------------------------------------------------
    def check_routes(self):
        cat = "routes"
        for rel, patterns in REQUIRED_ROUTES.items():
            path = ROOT / rel
            if not path.exists():
                self.add(cat, f"Route file exists: {rel}", False,
                         "missing", severity="high")
                continue
            content = path.read_text(encoding="utf-8")
            missing = [pat for pat in patterns if pat not in content]
            self.add(cat, f"Routes defined in {Path(rel).name}",
                     len(missing) == 0,
                     f"{len(patterns) - len(missing)}/{len(patterns)}",
                     detail={"missing": missing},
                     severity="medium")

    # -- Category 11: docs --------------------------------------------------
    def check_docs(self):
        cat = "docs"
        for name, min_lines in [
            ("README.md", 10),
            ("WORKFLOW.md", 50),
            ("HANDOFF.md", 100),
            ("AGENTS.md", 50),
            ("RESUME.md", 50),
        ]:
            path = ROOT / name
            if not path.exists():
                self.add(cat, f"{name} exists", False, "missing",
                         severity="medium")
                continue
            n = len(path.read_text(encoding="utf-8").splitlines())
            self.add(cat, f"{name} has reasonable size",
                     n >= min_lines,
                     f"{n} lines (min {min_lines})",
                     severity="low")

    # -- Category 12: pre-push gate -----------------------------------------
    def check_prepush(self):
        cat = "prepush"
        path = SCRIPTS / "pre_push_check.py"
        self.add(cat, "pre_push_check.py exists", path.exists(),
                 "found" if path.exists() else "missing",
                 severity="high")
        # Latest smoke test
        smokes = sorted(SCRIPTS.glob("smoke_test_part*.py"))
        self.add(cat, "At least one smoke_test_partNN.py",
                 len(smokes) > 0, f"{len(smokes)} found",
                 severity="medium")
        if smokes:
            self.add(cat, "Latest smoke test file",
                     True, smokes[-1].name, severity="low")

    # -- Category 13: git ---------------------------------------------------
    def check_git(self):
        cat = "git"
        # Clean working tree
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=10,
            )
            lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
            self.add(cat, "Git working tree clean",
                     len(lines) == 0,
                     f"{len(lines)} pending changes" if lines else "clean",
                     detail={"changes": lines[:5]},
                     severity="medium")
        except Exception as e:
            self.add(cat, "Git status checkable", None,
                     f"{type(e).__name__}: {e}", severity="low")

        # Unpushed commits
        try:
            r = subprocess.run(
                ["git", "rev-list", "--count", "origin/main..main"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=10,
            )
            n = int((r.stdout or "0").strip() or 0)
            self.add(cat, "No unpushed commits to GitHub",
                     n == 0, f"{n} unpushed",
                     severity="medium")
        except Exception:
            self.add(cat, "Git unpushed check", "skip", "skipped",
                     severity="low")

        # Latest commit info
        try:
            r = subprocess.run(
                ["git", "log", "-1", "--oneline"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=10,
            )
            line = (r.stdout or "").strip()
            self.add(cat, "Latest commit", True, line or "(empty)",
                     severity="low")
        except Exception:
            pass

    # -- Category 14: security ----------------------------------------------
    def check_security(self):
        cat = "security"
        # .env not tracked in git
        try:
            r = subprocess.run(
                ["git", "ls-files", "--error-unmatch", ".env"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=10,
            )
            tracked = r.returncode == 0
            self.add(cat, ".env NOT tracked in git", not tracked,
                     "safe (untracked)" if not tracked else "DANGER tracked",
                     severity="critical")
        except Exception:
            self.add(cat, ".env tracked check", "skip", "skipped",
                     severity="low")

        # Sandbox present
        sandbox = SRC / "sunnyware" / "tools" / "_sandbox.py"
        self.add(cat, "Sandbox runtime present", sandbox.exists(),
                 "found" if sandbox.exists() else "missing",
                 severity="high")

        # No hardcoded API keys in source (skip comments + docstrings)
        suspicious = []
        for f in (SRC / "sunnyware").rglob("*.py"):
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            # Collect docstring nodes to skip
            docstring_nodes = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef,
                                     ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, "body", None)
                    if body and isinstance(body[0], ast.Expr) and \
                            isinstance(body[0].value, ast.Constant) and \
                            isinstance(body[0].value.value, str):
                        docstring_nodes.add(id(body[0].value))
            # Only check string literals that aren't docstrings
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if id(node) in docstring_nodes:
                        continue
                    v = node.value
                    for token in ["gsk_", "sk-or-", "nvapi-", "AIza", "mstrl_"]:
                        # Only flag if followed by 15+ chars (looks like real key)
                        idx = v.find(token)
                        if idx >= 0 and len(v) - idx > len(token) + 15:
                            suspicious.append(
                                f"{f.relative_to(ROOT)}:{node.lineno}: {token}...")
                            break
        self.add(cat, "No hardcoded API keys in source",
                 len(suspicious) == 0,
                 f"{len(suspicious)} suspicious files",
                 detail={"files": suspicious[:5]},
                 severity="critical")

    # -- Category 15: hygiene -----------------------------------------------
    def check_hygiene(self):
        cat = "hygiene"
        # __pycache__ folders in src/scripts (should be gitignored, not deleted)
        pycache_count = len(list((SRC / "sunnyware").rglob("__pycache__")))
        self.add(cat, "__pycache__ present (gitignored)", True,
                 f"{pycache_count} folders (ignored by git)",
                 severity="low")
        # data/ dir
        data_dir = ROOT / "data"
        self.add(cat, "data/ dir exists",
                 data_dir.exists(),
                 "found" if data_dir.exists() else "missing",
                 severity="low")
        # Stale .bak.partN files
        baks = list(SCRIPTS.glob("*.bak.part*"))
        self.add(cat, "No stale .bak.partN files in scripts/",
                 len(baks) == 0,
                 f"{len(baks)} found (gitignored)",
                 severity="low")

    # -- Category 16: network (optional) ------------------------------------
    def check_network(self):
        cat = "network"
        try:
            import httpx
        except ImportError:
            self.add(cat, "httpx available for network checks",
                     None, "httpx not installed", severity="low")
            return
        # HF Space health
        try:
            r = httpx.get(
                "https://shamiur-sunnyware.hf.space/health/ready",
                timeout=10.0,
            )
            if r.status_code == 200:
                d = r.json()
                status = d.get("status")
                tools = (d.get("checks") or {}).get("tools")
                self.add(cat, "HF Space /health/ready returns ok",
                         status == "ok",
                         f"status={status}, tools={tools}",
                         severity="high")
            else:
                self.add(cat, "HF Space /health/ready returns ok",
                         None,
                         f"HTTP {r.status_code}",
                         severity="medium")
        except Exception as e:
            self.add(cat, "HF Space reachable",
                     None,
                     f"{type(e).__name__}: {e}",
                     severity="low")

        # Providers status
        try:
            r = httpx.get(
                "https://shamiur-sunnyware.hf.space/api/providers/status",
                timeout=10.0,
            )
            if r.status_code == 200:
                d = r.json()
                configured = d.get("configured", "")
                provs = d.get("providers", [])
                self.add(cat, "HF Space has 3+ providers configured",
                         len(provs) >= 3,
                         f"{len(provs)} providers: {configured}",
                         severity="high")
            else:
                self.add(cat, "HF Space providers endpoint", None,
                         f"HTTP {r.status_code}", severity="low")
        except Exception as e:
            self.add(cat, "HF Space providers reachable", None,
                     f"{type(e).__name__}", severity="low")


# -- Scoring ----------------------------------------------------------------

def compute_score(results):
    """Weighted score 0-100. critical=10, high=5, medium=3, low=1.
    FAIL removes all points; WARN removes half; SKIP removes none.
    Returns dict with total, breakdown by severity, grade."""
    by_sev = {"critical": [0, 0], "high": [0, 0],
              "medium": [0, 0], "low": [0, 0]}
    # [earned, possible]
    for r in results:
        w = SEVERITY_WEIGHTS.get(r.severity, 1)
        by_sev[r.severity][1] += w
        if r.status == "PASS":
            by_sev[r.severity][0] += w
        elif r.status == "WARN":
            by_sev[r.severity][0] += w * 0.5
        # FAIL, SKIP contribute 0

    total_earned = sum(v[0] for v in by_sev.values())
    total_possible = sum(v[1] for v in by_sev.values())
    if total_possible == 0:
        pct = 0.0
    else:
        pct = 100.0 * total_earned / total_possible

    if pct >= 95:
        grade = "A+ (production-ready)"
    elif pct >= 90:
        grade = "A (excellent)"
    elif pct >= 80:
        grade = "B (good, some warnings)"
    elif pct >= 70:
        grade = "C (usable, issues present)"
    elif pct >= 50:
        grade = "D (needs work)"
    else:
        grade = "F (critical failures)"

    return {
        "score": round(pct, 1),
        "grade": grade,
        "by_severity": {
            k: {"earned": round(v[0], 1), "possible": v[1]}
            for k, v in by_sev.items()
        },
    }


# -- Reporting --------------------------------------------------------------

def report_console(results, score_info, elapsed):
    """Human-readable console output."""
    print()
    print("#" * 72)
    print("# Sunnyware System Monitor")
    print("#" * 72)
    print()
    print("Started: " + datetime.now().isoformat(timespec="seconds"))
    print("Elapsed: " + str(round(elapsed, 2)) + "s")
    print()

    # Group by category
    by_cat = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    for cat in sorted(by_cat.keys()):
        print("-" * 72)
        print(" " + cat.upper())
        print("-" * 72)
        for r in by_cat[cat]:
            marker = {"PASS": "[PASS]", "FAIL": "[FAIL]",
                      "WARN": "[WARN]", "SKIP": "[SKIP]"}[r.status]
            print("  " + marker + " " + r.name + "  --  " + r.message)
            if r.detail and r.status == "FAIL":
                for k, v in r.detail.items():
                    if v:
                        print("      " + k + ": " + str(v)[:120])
        print()

    # Score
    print("=" * 72)
    print(" SCORE: " + str(score_info["score"]) + " / 100")
    print(" GRADE: " + score_info["grade"])
    print("=" * 72)
    by_sev = score_info["by_severity"]
    for sev in ["critical", "high", "medium", "low"]:
        v = by_sev[sev]
        pct = (100.0 * v["earned"] / v["possible"]) if v["possible"] else 100.0
        print("  " + sev.ljust(10) +
              " " + str(v["earned"]) + "/" + str(v["possible"]) +
              "  (" + str(round(pct, 1)) + "%)")
    print()

    # Summary counts
    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
    for r in results:
        counts[r.status] += 1
    print("  Checks: " + str(counts["PASS"]) + " pass, " +
          str(counts["FAIL"]) + " fail, " +
          str(counts["WARN"]) + " warn, " +
          str(counts["SKIP"]) + " skip")
    print()

    # Failures summary
    fails = [r for r in results if r.status == "FAIL"]
    if fails:
        print("=" * 72)
        print(" FAILURES TO FIX (by severity)")
        print("=" * 72)
        for sev in ["critical", "high", "medium", "low"]:
            sev_fails = [r for r in fails if r.severity == sev]
            if not sev_fails:
                continue
            print()
            print("  [" + sev.upper() + "]")
            for r in sev_fails:
                print("    - " + r.category + ": " + r.name)
                print("      " + r.message)
        print()

    # Known limitations (info only)
    if KNOWN_LIMITATIONS:
        print("=" * 72)
        print(" KNOWN LIMITATIONS (accepted, not scored)")
        print("=" * 72)
        for lim in KNOWN_LIMITATIONS:
            print("  - " + lim)
        print()

    # Pending features roadmap
    if PENDING_FEATURES:
        print("=" * 72)
        print(" ROADMAP / PENDING FEATURES")
        print("=" * 72)
        for feat in PENDING_FEATURES:
            line = "  - " + feat.get("id", "?") + ": " + feat.get("title", "?")
            extra = []
            if "priority" in feat:
                extra.append("priority=" + feat["priority"])
            if "effort" in feat:
                extra.append("effort=" + feat["effort"])
            if "blocker" in feat:
                extra.append("blocker=" + feat["blocker"])
            if extra:
                line += "  (" + ", ".join(extra) + ")"
            print(line)
        print()

    print("=" * 72)
    if score_info["score"] >= 95:
        print(" VERDICT: PRODUCTION-READY")
    elif score_info["score"] >= 85:
        print(" VERDICT: GOOD - minor warnings only")
    elif score_info["score"] >= 70:
        print(" VERDICT: USABLE - non-critical issues present")
    else:
        print(" VERDICT: NEEDS ATTENTION")
    print("=" * 72)
    print()


def report_markdown(results, score_info, elapsed):
    """Write reports/system_health.md."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "system_health.md"
    lines = []
    lines.append("# Sunnyware System Health Report")
    lines.append("")
    lines.append("**Generated:** " + datetime.now().isoformat(timespec="seconds"))
    lines.append("**Elapsed:** " + str(round(elapsed, 2)) + "s")
    lines.append("**Score:** " + str(score_info["score"]) + " / 100")
    lines.append("**Grade:** " + score_info["grade"])
    lines.append("")
    lines.append("## Severity breakdown")
    lines.append("")
    lines.append("| Severity | Earned | Possible | Percent |")
    lines.append("|----------|--------|----------|---------|")
    for sev in ["critical", "high", "medium", "low"]:
        v = score_info["by_severity"][sev]
        pct = (100.0 * v["earned"] / v["possible"]) if v["possible"] else 100.0
        lines.append("| " + sev + " | " + str(v["earned"]) + " | " +
                     str(v["possible"]) + " | " +
                     str(round(pct, 1)) + "% |")
    lines.append("")

    # By category
    by_cat = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)
    lines.append("## Checks by category")
    lines.append("")
    for cat in sorted(by_cat.keys()):
        lines.append("### " + cat)
        lines.append("")
        for r in by_cat[cat]:
            icon = {"PASS": "+", "FAIL": "X", "WARN": "!",
                    "SKIP": "-"}[r.status]
            lines.append("- `[" + icon + "]` **" + r.name + "** - " + r.message)
        lines.append("")

    # Failures
    fails = [r for r in results if r.status == "FAIL"]
    if fails:
        lines.append("## Failures to fix")
        lines.append("")
        for r in fails:
            lines.append("- **[" + r.severity + "]** " + r.category +
                         " / " + r.name + " - " + r.message)
            if r.detail:
                for k, v in r.detail.items():
                    if v:
                        lines.append("    - " + k + ": `" + str(v)[:200] + "`")
        lines.append("")

    lines.append("## Known limitations (accepted)")
    lines.append("")
    for lim in KNOWN_LIMITATIONS:
        lines.append("- " + lim)
    lines.append("")

    lines.append("## Roadmap / pending features")
    lines.append("")
    for feat in PENDING_FEATURES:
        lines.append("- **" + feat.get("title", "?") + "** - " +
                     str(feat.get("blocker", feat.get("effort", "TBD"))))
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def report_json(results, score_info, elapsed):
    """Write reports/system_health.json."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "system_health.json"
    payload = {
        "generated": datetime.now().isoformat(),
        "elapsed_s": round(elapsed, 2),
        "score": score_info,
        "results": [r.to_dict() for r in results],
        "known_limitations": KNOWN_LIMITATIONS,
        "pending_features": PENDING_FEATURES,
    }
    out.write_text(json.dumps(payload, indent=2, default=str),
                   encoding="utf-8")
    return out


# -- Baseline diff ----------------------------------------------------------

def save_baseline(results, score_info):
    payload = {
        "generated": datetime.now().isoformat(),
        "score": score_info["score"],
        "grade": score_info["grade"],
        "checks": {r.category + "/" + r.name: r.status for r in results},
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return BASELINE_PATH


def diff_baseline(results):
    if not BASELINE_PATH.exists():
        return "No baseline yet. Run with --baseline first."
    try:
        old = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return "Could not read baseline: " + str(e)

    old_checks = old.get("checks", {})
    new_checks = {r.category + "/" + r.name: r.status for r in results}

    improvements = []
    regressions = []
    new_checks_list = []
    removed_checks_list = []

    for k, v in new_checks.items():
        if k not in old_checks:
            new_checks_list.append(k)
        elif old_checks[k] != v:
            if v == "PASS" and old_checks[k] in ("FAIL", "WARN"):
                improvements.append(k + ": " + old_checks[k] + " -> PASS")
            elif v in ("FAIL", "WARN") and old_checks[k] == "PASS":
                regressions.append(k + ": PASS -> " + v)
    for k in old_checks:
        if k not in new_checks:
            removed_checks_list.append(k)

    lines = []
    lines.append("Baseline: " + old.get("generated", "?") +
                 " (score " + str(old.get("score", "?")) + ")")
    lines.append("")
    if improvements:
        lines.append("IMPROVEMENTS (" + str(len(improvements)) + "):")
        for x in improvements:
            lines.append("  + " + x)
        lines.append("")
    if regressions:
        lines.append("REGRESSIONS (" + str(len(regressions)) + "):")
        for x in regressions:
            lines.append("  - " + x)
        lines.append("")
    if new_checks_list:
        lines.append("NEW CHECKS (" + str(len(new_checks_list)) + "):")
        for x in new_checks_list[:10]:
            lines.append("  * " + x)
        lines.append("")
    if removed_checks_list:
        lines.append("REMOVED CHECKS (" + str(len(removed_checks_list)) + "):")
        for x in removed_checks_list[:10]:
            lines.append("  x " + x)
        lines.append("")
    if not (improvements or regressions or new_checks_list or
            removed_checks_list):
        lines.append("No changes since baseline.")
    return "\n".join(lines)


# -- Main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sunnyware System Monitor")
    parser.add_argument("--offline", action="store_true",
                        help="skip all network checks")
    parser.add_argument("--quick", action="store_true",
                        help="fast mode (also skips network)")
    parser.add_argument("--json", action="store_true",
                        help="output JSON only")
    parser.add_argument("--verbose", action="store_true",
                        help="verbose output")
    parser.add_argument("--baseline", action="store_true",
                        help="save current run as baseline")
    parser.add_argument("--diff", action="store_true",
                        help="compare to baseline")
    parser.add_argument("--watch", type=int, default=0,
                        help="loop every N seconds")
    args = parser.parse_args()

    if args.watch > 0:
        while True:
            try:
                run_once(args)
            except KeyboardInterrupt:
                print()
                print("watch stopped")
                return 0
            print("sleeping " + str(args.watch) + "s...")
            try:
                time.sleep(args.watch)
            except KeyboardInterrupt:
                print()
                print("watch stopped")
                return 0

    return run_once(args)


def run_once(args):
    t_start = time.time()
    monitor = Monitor(offline=args.offline, quick=args.quick,
                      verbose=args.verbose)
    try:
        monitor.run_checks()
    except Exception as e:
        print("MONITOR CRASH: " + type(e).__name__ + ": " + str(e))
        return 2

    elapsed = time.time() - t_start
    score_info = compute_score(monitor.results)

    if args.json:
        report_json(monitor.results, score_info, elapsed)
        payload = {
            "score": score_info["score"],
            "grade": score_info["grade"],
            "results": [r.to_dict() for r in monitor.results],
        }
        print(json.dumps(payload, indent=2, default=str))
    else:
        report_console(monitor.results, score_info, elapsed)
        md = report_markdown(monitor.results, score_info, elapsed)
        js = report_json(monitor.results, score_info, elapsed)
        print("Reports saved:")
        print("  " + str(md.relative_to(ROOT)))
        print("  " + str(js.relative_to(ROOT)))
        print()
        if args.diff:
            print("=" * 72)
            print(" DIFF VS BASELINE")
            print("=" * 72)
            print(diff_baseline(monitor.results))
            print()

    if args.baseline:
        path = save_baseline(monitor.results, score_info)
        print("Baseline saved: " + str(path.relative_to(ROOT)))
        print()

    fails = [r for r in monitor.results if r.status == "FAIL"]
    warns = [r for r in monitor.results if r.status == "WARN"]
    if fails:
        return 2
    if warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
