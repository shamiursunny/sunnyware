#!/usr/bin/env python3
"""Part 83 smoke test - webhook receiver."""
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
    print(" Part 83 - webhook receiver")
    print("=" * 62)

    core = ROOT / "src/sunnyware/webhook.py"
    route = ROOT / "src/sunnyware/routes/webhooks.py"
    check("webhook.py exists", core.exists())
    check("routes/webhooks.py exists", route.exists())
    check("migration 008 exists",
          (ROOT / "migrations/008_webhooks.sql").exists())
    if not core.exists() or not route.exists():
        return 1

    src = core.read_text(encoding="utf-8")
    check("add() defined", "async def add(" in src)
    check("list_all() defined", "async def list_all(" in src)
    check("delete() defined", "async def delete(" in src)
    check("events() defined", "async def events(" in src)
    check("fire() defined", "async def fire(" in src)
    check("token prefix wh_", '"wh_"' in src)

    try:
        ast.parse(src); check("webhook.py parses", True)
    except SyntaxError as e:
        check("webhook.py parses", False, detail=str(e))

    route_src = route.read_text(encoding="utf-8")
    check("POST /webhook/{token} route", '@router.post("/webhook/{token}")' in route_src)

    main_src = (ROOT / "src/sunnyware/main.py").read_text(encoding="utf-8")
    check("route registered in main", "webhooks_routes" in main_src)

    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")
    for mod, cls in [
        ("webhook_add", "WebhookAddTool"),
        ("webhook_list", "WebhookListTool"),
        ("webhook_delete", "WebhookDeleteTool"),
        ("webhook_events", "WebhookEventsTool"),
    ]:
        f = ROOT / "src" / "sunnyware" / "tools" / (mod + ".py")
        check(mod + ".py exists", f.exists())
        if f.exists():
            s = f.read_text(encoding="utf-8")
            check(mod + " class", "class " + cls in s)
        check(cls + " registered", cls + ".name: " + cls + "()" in init_src)

    # Integration: needs DB pool
    async def run_db():
        from sunnyware import state as _st
        from sunnyware.runtime import init_state
        init_state()
        await _st.init_pool()

        from sunnyware.webhook import add, list_all, delete, events, fire

        r = await add("smoke_p83", trigger_prompt="", notify_email="")
        check("add succeeds", "error" not in r and r.get("ok") is True,
              detail=str(r)[:200] if r.get("error") else "")
        tok = r.get("token")
        check("token starts with wh_", bool(tok and tok.startswith("wh_")))
        check("url_path returned", bool(r.get("url_path", "").startswith("/webhook/")))

        r2 = await list_all()
        check("list_all succeeds", "error" not in r2)
        if "error" not in r2:
            toks = [e["token"] for e in r2.get("endpoints", [])]
            check("smoke_p83 in list", tok in toks)

        # fire the webhook (no trigger prompt -> just store)
        payload = {"event": "test", "amount": 42}
        r3 = await fire(tok, payload, {"User-Agent": "smoke"}, "127.0.0.1")
        check("fire succeeds", r3.get("ok") is True,
              detail=str(r3)[:200] if not r3.get("ok") else "")
        check("event_id returned", isinstance(r3.get("event_id"), int))

        r4 = await events(tok, limit=5)
        check("events listed", "error" not in r4 and r4.get("count", 0) >= 1)

        # unknown token
        r5 = await fire("wh_bogus_xyz", {}, {}, "")
        check("unknown token rejected", r5.get("ok") is False)

        # delete
        r6 = await delete(tok)
        check("delete succeeds", "error" not in r6 and r6.get("ok") is True)

    try:
        asyncio.run(run_db())
    except Exception as e:
        check("DB integration", False, detail=type(e).__name__ + ": " + str(e)[:150])

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
