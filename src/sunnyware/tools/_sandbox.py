# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Sandboxed execution runtime for the agent's data workbench.

Design goals:
  1. Rich library access (pandas, numpy, matplotlib, SQL, etc.)
  2. Reasonable jail: no os/subprocess/network; workspace-confined paths
  3. Old-laptop safe: respects SUNNYWARE_CPU_THREADS via rag._threads
  4. Graceful timeouts and output caps

Threat model:
  Semi-trusted code (from the agent's own LLM). Not a true adversarial
  sandbox. If the HF Space is shared publicly, enable API auth (Part 21).
"""

import ast
import base64
import io
import os
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path


# ── Limits ──
MAX_CODE_BYTES = 32 * 1024
MAX_OUTPUT_CHARS = 64 * 1024
DEFAULT_TIMEOUT = float(os.getenv("SUNNYWARE_PY_EVAL_TIMEOUT", "30"))


# ── Module whitelist ──
# Submodules must be listed explicitly (urllib.parse OK, urllib.request NOT).
ALLOWED_MODULES = frozenset({
    # stdlib — safe/useful
    "json", "csv", "math", "statistics", "datetime", "time", "re",
    "collections", "itertools", "functools", "decimal", "fractions",
    "random", "string", "textwrap", "difflib", "enum", "dataclasses",
    "typing", "copy", "uuid", "base64", "hashlib", "hmac", "secrets",
    "io", "sqlite3", "zoneinfo", "calendar",
    "html", "xml.etree.ElementTree", "urllib.parse",
    "warnings", "contextlib", "operator", "array", "struct",
    "bisect", "heapq", "queue",
    # numeric / data
    "numpy", "pandas", "scipy", "scipy.stats", "scipy.optimize",
    "scipy.linalg", "scipy.signal", "scipy.interpolate",
    "sklearn", "statsmodels",
    "pyarrow", "pyarrow.parquet",
    "duckdb",
    # viz
    "matplotlib", "matplotlib.pyplot", "seaborn", "plotly",
    "plotly.express", "plotly.graph_objects",
    # excel / output
    "openpyxl", "xlsxwriter", "tabulate",
})


# ── Banned names ──
BANNED_NAMES = frozenset({
    "eval", "exec", "compile", "__import__", "input", "open",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "breakpoint", "help", "exit", "quit",
    "__builtins__", "__loader__", "__spec__", "__file__", "__cached__",
    "memoryview", "classmethod", "staticmethod", "property", "super",
    "object",
})


# ── AST validation ──
def _is_module_allowed(name: str) -> bool:
    if not name:
        return False
    if name in ALLOWED_MODULES:
        return True
    # Allow submodules whose immediate parent is whitelisted.
    # E.g. numpy.linalg OK if numpy is whitelisted;
    # urllib.request blocked since only urllib.parse is whitelisted.
    if "." in name:
        parent = name.rsplit(".", 1)[0]
        if parent in ALLOWED_MODULES:
            return True
    return False


class _SandboxVisitor(ast.NodeVisitor):
    def __init__(self):
        self.errors = []

    def visit_Import(self, node):
        for alias in node.names:
            if not _is_module_allowed(alias.name):
                self.errors.append(
                    "import '" + alias.name + "' not allowed (line " + str(node.lineno) + ")"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and not _is_module_allowed(node.module):
            self.errors.append(
                "from-import '" + node.module + "' not allowed (line " + str(node.lineno) + ")"
            )
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in BANNED_NAMES:
            self.errors.append(
                "banned name '" + node.id + "' (line " + str(node.lineno) + ")"
            )
        self.generic_visit(node)

    SAFE_DUNDERS = frozenset({
        "__name__", "__doc__", "__version__", "__all__",
    })

    BLOCKED_ATTRS = frozenset({
        "modules",         # sys.modules / sys.modules[...]
        "__globals__",     # func.__globals__
        "__code__",        # func.__code__
        "__subclasses__",  # object.__subclasses__() escape
        "__mro__", "__bases__",
        "__init_subclass__", "__class_getitem__",
    })

    def visit_Attribute(self, node):
        if node.attr in self.BLOCKED_ATTRS:
            self.errors.append(
                "attribute '" + node.attr + "' not allowed (line " + str(node.lineno) + ")"
            )
        if node.attr.startswith("__") and node.attr.endswith("__"):
            if node.attr not in self.SAFE_DUNDERS:
                self.errors.append(
                    "dunder attribute '" + node.attr + "' not allowed (line " + str(node.lineno) + ")"
                )
        self.generic_visit(node)


def validate(code: str) -> list:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        return ["syntax error: " + str(e.msg) + " (line " + str(e.lineno) + ")"]
    v = _SandboxVisitor()
    v.visit(tree)
    return v.errors


# ── Restricted builtins ──
def safe_builtins() -> dict:
    import builtins as _b
    allowed = [
        # core types
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
        "callable", "chr", "complex", "dict", "divmod", "enumerate", "filter",
        "float", "format", "frozenset", "hash", "hex", "id", "int",
        "isinstance", "issubclass", "iter", "len", "list", "map", "max",
        "min", "next", "oct", "ord", "pow", "print", "range", "repr",
        "reversed", "round", "set", "slice", "sorted", "str", "sum",
        "tuple", "type", "zip", "__build_class__",
        # constants
        "True", "False", "None", "NotImplemented", "Ellipsis",
        # exceptions
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "ZeroDivisionError", "ArithmeticError", "StopIteration",
        "AttributeError", "RuntimeError", "NameError", "AssertionError",
        "LookupError", "MemoryError", "OverflowError", "ImportError",
        "FileNotFoundError", "PermissionError", "OSError", "IOError",
        "UnicodeDecodeError", "UnicodeError", "NotImplementedError",
        "KeyboardInterrupt",
    ]
    return {name: getattr(_b, name) for name in allowed if hasattr(_b, name)}


# ── Jailed Path (subclass so we don't affect the real pathlib.Path) ──
MAX_READ_BYTES = 50 * 1024 * 1024  # 50 MB


def _make_jailed_path():
    from pathlib import Path as _RealPath

    class JailedPath(_RealPath):
        def read_text(self, *args, **kwargs):
            try:
                if self.exists() and self.stat().st_size > MAX_READ_BYTES:
                    raise ValueError(
                        "file too large (" + str(self.stat().st_size)
                        + " bytes, max " + str(MAX_READ_BYTES) + ")"
                    )
            except ValueError:
                raise
            except Exception:
                pass
            return super().read_text(*args, **kwargs)

        def read_bytes(self):
            try:
                if self.exists() and self.stat().st_size > MAX_READ_BYTES:
                    raise ValueError(
                        "file too large (" + str(self.stat().st_size)
                        + " bytes, max " + str(MAX_READ_BYTES) + ")"
                    )
            except ValueError:
                raise
            except Exception:
                pass
            return super().read_bytes()

    return JailedPath


# ── Custom __import__ ──
# Modules no code — user OR library — may import through our hook.
# Kept tight on purpose: defense-in-depth against library escapes.
ALWAYS_BANNED = frozenset({
    "os", "subprocess", "socket", "ctypes", "importlib",
    "multiprocessing", "pty", "tty", "fcntl", "termios",
})


def _make_import():
    import builtins as _b
    real_import = _b.__import__

    def sandbox_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level and level > 0:
            raise ImportError("relative imports not allowed")

        # Permanent ban — even library internals can't reach these
        base = (name or "").split(".")[0]
        if base in ALWAYS_BANNED:
            raise ImportError("module '" + name + "' is permanently banned")

        # Detect caller type via __name__ in caller's globals dict.
        # Only block when we can POSITIVELY identify user-exec context.
        # Unknown/None globals (C extensions) are trusted.
        caller = ""
        if isinstance(globals, dict):
            caller = globals.get("__name__", "") or ""
        is_user_code = caller in ("__main__", "<data_eval>", "__data_eval__")

        # User code path — apply whitelist
        if is_user_code:
            if not _is_module_allowed(name):
                raise ImportError(
                    "module '" + name + "' is not allowed in the sandbox"
                )
            if fromlist:
                for item in fromlist:
                    full = name + "." + item if name else item
                    if not _is_module_allowed(full) and not _is_module_allowed(name):
                        raise ImportError(
                            "module '" + full + "' is not allowed"
                        )

        # Library code path — trust transitive deps (duckdb, pandas, etc.)
        return real_import(name, globals, locals, fromlist, level)

    return sandbox_import


# ── matplotlib Agg backend (must run before pyplot import) ──
def _install_matplotlib_agg():
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        return True
    except Exception:
        return False


_MPL_OK = _install_matplotlib_agg()


# ── Workspace jail helper ──
def _is_in_jail(p, ws) -> bool:
    try:
        return p.resolve().is_relative_to(ws.resolve())
    except AttributeError:
        s = str(p.resolve()); w = str(ws.resolve())
        return s == w or s.startswith(w + os.sep)


def ws_path(rel: str):
    """Resolve a workspace-relative path, jailed. Use this instead of raw Path()."""
    from .. import paths as _paths
    ws = _paths.workspace().resolve()
    if not rel:
        raise PermissionError("empty path not allowed")
    if rel.startswith("/") or (len(rel) > 1 and rel[1] == ":"):
        raise PermissionError("absolute paths not allowed: " + rel)
    p = (ws / rel).resolve()
    if not _is_in_jail(p, ws):
        raise PermissionError("path escapes workspace: " + rel)
    return p


# ── Globals for exec ──
def build_globals() -> dict:
    """Build the exec() namespace with preloaded popular libraries."""
    sb = safe_builtins()
    sb["__import__"] = _make_import()
    g = {"__builtins__": sb}

    loaders = [
        ("np",            "numpy"),
        ("pd",            "pandas"),
        ("plt",           "matplotlib.pyplot"),
        ("sns",           "seaborn"),
        ("scipy",         "scipy"),
        ("stats",         "scipy.stats"),
        ("sklearn",       "sklearn"),
        ("sqlite3",       "sqlite3"),
        ("duckdb",        "duckdb"),
        ("pa",            "pyarrow"),
        ("openpyxl",      "openpyxl"),
        ("tabulate",      "tabulate"),
        ("Path",          "__jailed_path__"),  # injected below
        ("ws_path",       None),  # injected below
        ("_workspace",    None),  # injected below
    ]
    g["_JailedPath"] = _make_jailed_path()

    for alias, modname in loaders:
        if modname is None:
            continue
        if modname == "__jailed_path__":
            g[alias] = g["_JailedPath"]
            continue
        try:
            mod = __import__(modname, fromlist=[modname.split(".")[-1]])
            g[alias] = mod
        except Exception as e:
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "sandbox_import_failed module=" + modname + " err=" + str(e)
            )
            g[alias] = None

    # ── Security: disable sqlite3 extension loading (native code exec) ──
    if g.get("sqlite3") is not None:
        try:
            def _blocked(*_a, **_k):
                raise PermissionError("sqlite3 extension loading is disabled")
            g["sqlite3"].enable_load_extension = _blocked
            g["sqlite3"].Connection.enable_load_extension = _blocked
        except Exception:
            pass

    g["ws_path"] = ws_path
    try:
        from .. import paths as _paths
        g["_workspace"] = str(_paths.workspace())
    except Exception:
        g["_workspace"] = "."

    # Convenience: sql_on(df, "SELECT ... FROM df ...") -> pandas DataFrame
    def sql_on(df, query, name="df"):
        """Run DuckDB SQL over a pandas DataFrame. Returns pandas DataFrame."""
        import duckdb as _dd
        conn = _dd.connect(":memory:")  # no disk spill — HF /data is persistent, don't fill it
        try:
            conn.register(name, df)
            return conn.execute(query).fetchdf()
        finally:
            conn.close()

    g["sql_on"] = sql_on
    return g


# ── Exec core ──
def exec_code(code: str, g: dict) -> dict:
    """Run code in the given namespace. Timeout/cancellation handled by caller."""
    out = io.StringIO()
    t0 = time.time()
    error = None
    try:
        with redirect_stdout(out), redirect_stderr(out):
            compiled = compile(code, "<data_eval>", "exec")
            exec(compiled, g)
    except SystemExit:
        error = "SystemExit blocked"
    except BaseException as e:
        error = type(e).__name__ + ": " + str(e)
    elapsed_ms = int((time.time() - t0) * 1000)
    return {
        "ok": error is None,
        "error": error,
        "stdout": out.getvalue()[:MAX_OUTPUT_CHARS],
        "result": _safe_repr(g.get("result")),
        "elapsed_ms": elapsed_ms,
    }


def _safe_repr(v):
    if v is None:
        return None
    # Auto-convert DataFrames / Series to JSON records for clean agent output
    try:
        import json as _j
        tname = type(v).__name__
        if tname == "DataFrame" and hasattr(v, "to_dict"):
            records = v.head(1000).to_dict(orient="records")
            s = _j.dumps(records, default=str)
            return s[:MAX_OUTPUT_CHARS]
        if tname == "Series" and hasattr(v, "tolist"):
            s = _j.dumps(v.tolist(), default=str)
            return s[:MAX_OUTPUT_CHARS]
    except Exception:
        pass
    try:
        s = repr(v)
        return s[:MAX_OUTPUT_CHARS]
    except Exception:
        return "<unrepresentable " + type(v).__name__ + ">"


# ── Chart capture ──
def capture_chart(plt_mod) -> dict:
    """If any matplotlib figures are open, render the latest as base64 PNG.
    Returns {"image_base64": ..., "image_format": "png", "image_bytes": N}
    or {} if nothing to capture."""
    if plt_mod is None:
        return {}
    try:
        figs = plt_mod.get_fignums()
        if not figs:
            return {}
        MAX_CHART_BYTES = 200 * 1024  # 200 KB
        buf = io.BytesIO()
        plt_mod.gcf().savefig(buf, format="png", bbox_inches="tight", dpi=100)
        raw = buf.getvalue()
        # Retry at lower DPI if too large
        if len(raw) > MAX_CHART_BYTES:
            buf = io.BytesIO()
            plt_mod.gcf().savefig(buf, format="png", bbox_inches="tight", dpi=60)
            raw = buf.getvalue()
        plt_mod.close("all")
        if len(raw) > MAX_CHART_BYTES:
            return {
                "image_error": "chart too large even at low DPI (>"
                               + str(MAX_CHART_BYTES) + " bytes)",
            }
        return {
            "image_base64": base64.b64encode(raw).decode("ascii"),
            "image_format": "png",
            "image_bytes": len(raw),
        }
    except Exception:
        return {}
