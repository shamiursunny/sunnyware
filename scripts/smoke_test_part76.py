#!/usr/bin/env python3
"""Part 76 smoke test - email tools + KPI email wiring."""
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
        PASS += 1; print("  [PASS] " + label)
    else:
        FAIL += 1; print("  [FAIL] " + label + (" - " + detail if detail else ""))


def main():
    print("=" * 62)
    print(" Part 76 - email tools + KPI email wiring")
    print("=" * 62)

    check("email_send.py exists", (ROOT / "src/sunnyware/email_send.py").exists())
    check("migration 005", (ROOT / "migrations/005_email_send_log.sql").exists())
    check("migration 006", (ROOT / "migrations/006_kpi_watch_email.sql").exists())

    core = (ROOT / "src/sunnyware/email_send.py").read_text(encoding="utf-8")
    check("send_email defined", "async def send_email" in core)
    check("list_sent defined", "async def list_sent" in core)
    check("is_configured defined", "def is_configured" in core)
    check("config_summary defined", "def config_summary" in core)
    check("uses smtplib", "smtplib.SMTP" in core)
    check("STARTTLS used", "starttls" in core)
    check("attachment cap", "_MAX_ATTACH_BYTES" in core)

    try:
        ast.parse(core); check("email_send.py parses", True)
    except SyntaxError as e:
        check("email_send.py parses", False, detail=str(e))

    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")
    for mod, cls in [
        ("email_send", "EmailSendTool"),
        ("email_list_sent", "EmailListSentTool"),
        ("email_configured", "EmailConfiguredTool"),
    ]:
        f = ROOT / "src" / "sunnyware" / "tools" / (mod + ".py")
        check(mod + ".py exists", f.exists())
        if f.exists():
            s = f.read_text(encoding="utf-8")
            check(mod + " class", "class " + cls in s)
        check(cls + " registered", cls + ".name: " + cls + "()" in init_src)

    kw = (ROOT / "src/sunnyware/kpi_watch.py").read_text(encoding="utf-8")
    check("add_watch has notify_email", "notify_email" in kw)
    check("run_watch sends email", "email_send" in kw)

    from sunnyware.email_send import config_summary, is_configured
    summary = config_summary()
    check("config_summary has configured key", "configured" in summary)
    check("default host smtp.gmail.com", summary.get("host") == "smtp.gmail.com")

    async def run(**kw2):
        from sunnyware.email_send import send_email
        return await send_email(**kw2)

    check("empty to rejected", "error" in asyncio.run(run(to=[], subject="x", body="y")))
    check("invalid email rejected", "error" in asyncio.run(run(to=["bad-email"], subject="x", body="y")))
    check("empty subject rejected", "error" in asyncio.run(run(to=["a@b.com"], subject="", body="y")))
    check("empty body rejected", "error" in asyncio.run(run(to=["a@b.com"], subject="x", body="")))

    if not is_configured():
        r5 = asyncio.run(run(to=["a@b.com"], subject="x", body="y"))
        check("unconfigured returns setup_hint",
              "setup_hint" in r5 or "SMTP not configured" in str(r5))
    else:
        check("SMTP configured (local send skipped)", True)

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
