"""Unit tests for Sunnyware diagnostics."""
from sunnyware.diagnostics import checks_startup, checks_preflight, checks_percall, checks_postresponse

def test_duplicate_tool_names(monkeypatch):
    monkeypatch.setattr(checks_startup, "_tool_names", lambda: ["a", "b", "a"])
    recs = checks_startup.check_registry_integrity()
    assert any(r.cls == "registry_integrity" for r in recs)

def test_recursive_name(monkeypatch):
    monkeypatch.setattr(checks_startup, "_tool_names",
                        lambda: ["email_send_and_attachments_and_attachments"])
    recs = checks_startup.check_registry_integrity()
    assert any("Recursive" in r.message for r in recs)

def test_percall_auth_error():
    recs = checks_percall.run("t", {}, {"error": "HTTP 401: unauthorized"}, 0.1)
    assert any(r.cls == "execution" and "auth" in r.message.lower() for r in recs)

def test_postresponse_contradiction(monkeypatch):
    monkeypatch.setattr(checks_postresponse, "_registry",
                        lambda: {"citation_lookup"})
    recs = checks_postresponse.run("I don't have any citation tools")
    assert any(r.cls == "llm_self_report_inconsistency" for r in recs)

def test_preflight_unregistered(monkeypatch):
    monkeypatch.setattr(checks_preflight, "_registry", lambda: {"email_send"})
    recs = checks_preflight.run("do x", {"tool": "ghost_tool"})
    assert any(r.cls == "routing_anomaly" for r in recs)
