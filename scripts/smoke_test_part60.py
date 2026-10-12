#!/usr/bin/env python3
"""Part 60 smoke test — workspace_snapshot tool."""
import ast, base64, io, os, sys, asyncio, zipfile
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
    print(" Part 60 — workspace_snapshot tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/workspace_snapshot.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("workspace_snapshot.py exists", tool_file.exists())
    if not tool_file.exists():
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class WorkspaceSnapshotTool" in src)
    check("name = workspace_snapshot", 'name = "workspace_snapshot"' in src)
    check("uses zipfile", "zipfile.ZipFile" in src)
    check("workspace jail", "_workspace_root" in src)
    check("skip dirs list", "_SKIP_DIRS" in src)
    check("max files cap", "_MAX_FILES" in src)
    check("max bytes cap", "_MAX_TOTAL_BYTES" in src)
    check("base64 return cap", "_MAX_RETURN_BYTES" in src)
    check("registered in __init__",
          "WorkspaceSnapshotTool.name: WorkspaceSnapshotTool()" in init_src)

    try:
        ast.parse(src)
        check("workspace_snapshot.py parses", True)
    except SyntaxError as e:
        check("workspace_snapshot.py parses", False, detail=str(e))

    # Integration — create a small subdirectory and snapshot it
    ws = Path(os.getenv("SUNNYWARE_WORKSPACE") or "/data/workspace").resolve()
    sub = ws / "snapshot_p60_test"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "a.txt").write_text("hello\n", encoding="utf-8")
    (sub / "b.txt").write_text("world\n" * 100, encoding="utf-8")
    (sub / "sub").mkdir(exist_ok=True)
    (sub / "sub" / "c.txt").write_text("nested\n", encoding="utf-8")
    # A skipped file type
    (sub / "junk.pyc").write_bytes(b"\x00" * 10)

    async def run(**kw):
        from sunnyware.tools.workspace_snapshot import WorkspaceSnapshotTool
        return await WorkspaceSnapshotTool().run(kw)

    r = asyncio.run(run(subpath="snapshot_p60_test",
                        name="p60_smoke.zip"))
    check("snapshot succeeds", "error" not in r,
          detail=str(r)[:200] if r.get("error") else "")
    if "error" not in r:
        check("files_added == 3 (a, b, sub/c)",
              r.get("files_added") == 3,
              detail=f"got {r.get('files_added')}")
        check("returned base64", r.get("returned_base64") is True)
        check("zip_bytes > 0", r.get("zip_bytes", 0) > 0)
        check("compression_ratio < 1", (r.get("compression_ratio") or 1) < 1)

        # Verify the zip is actually valid
        if r.get("base64"):
            try:
                raw = base64.b64decode(r["base64"])
                zf = zipfile.ZipFile(io.BytesIO(raw))
                names = zf.namelist()
                check("zip contains 3 entries", len(names) == 3,
                      detail=f"got {names}")
                check("zip has a.txt",
                      any("a.txt" in n for n in names))
                check("zip has sub/c.txt",
                      any(n.endswith("sub/c.txt") for n in names))
                check("zip excludes .pyc",
                      not any(n.endswith(".pyc") for n in names))
                zf.close()
            except Exception as e:
                check("zip valid", False, detail=str(e))

    # Rejections
    r2 = asyncio.run(run(subpath="../../../etc"))
    check("subpath escape rejected", "error" in r2)

    r3 = asyncio.run(run(subpath="does-not-exist-xyz"))
    check("missing subpath rejected", "error" in r3)

    # Whole workspace (default)
    r4 = asyncio.run(run(name="p60_whole.zip", include_base64=False))
    check("whole workspace snapshot succeeds", "error" not in r4,
          detail=str(r4)[:120] if r4.get("error") else "")
    if "error" not in r4:
        check("whole ws files_added > 0", r4.get("files_added", 0) > 0)
        check("whole ws returned_base64 is False (disabled)",
              r4.get("returned_base64") is False)

    # Cleanup
    import shutil
    try: shutil.rmtree(sub)
    except Exception: pass
    for n in ("p60_smoke.zip", "p60_whole.zip"):
        try: (ws / n).unlink()
        except Exception: pass

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
