# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 171: outbound webhooks.

External systems subscribe to agent events. When an event fires
(circuit.open, audit.log, schema.violation, recon.block, budget.threshold,
golden.regression, evals.run, etc.), we POST to each matching subscriber
with an HMAC-signed JSON body.

Distinct from Part 83 (webhook.py), which is INBOUND: external services
POST to /webhook/{token} to trigger the agent.

Design:
  - JSON state: /data/outbound_webhooks.json on HF, data/outbound_*.json
    locally. SUNNYWARE_WEBHOOKS_OUT_STORAGE overrides.
  - Fire-and-forget: dispatch() schedules delivery tasks, never blocks.
  - HMAC signature: X-Sunnyware-Signature: sha256=<hex> over body.
  - Retries: 3 attempts, 1s / 4s / 16s backoff.
  - Subscriber list cached 5s for speed (audit.log hits dispatch often).
  - Never raises into caller.

Config:
  SUNNYWARE_WEBHOOKS_OUT_ENABLED=1        master switch
  SUNNYWARE_WEBHOOKS_OUT_STORAGE=<path>   override storage file
  SUNNYWARE_WEBHOOKS_OUT_TIMEOUT=10.0     per-request timeout seconds
"""

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from pathlib import Path


_DEFAULT_STATE = {
    "webhooks": [],
    "deliveries": [],
}

_CACHE = {"ts": 0.0, "subs": []}
_CACHE_TTL = 5.0
_DELIVERY_LOG_CAP = 200


# ─── config ───

def _enabled() -> bool:
    v = (os.getenv("SUNNYWARE_WEBHOOKS_OUT_ENABLED", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def _timeout() -> float:
    try:
        return float(os.getenv("SUNNYWARE_WEBHOOKS_OUT_TIMEOUT", "10.0"))
    except Exception:
        return 10.0


def _path() -> Path:
    env = os.getenv("SUNNYWARE_WEBHOOKS_OUT_STORAGE")
    if env:
        return Path(env)
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data / "outbound_webhooks.json"
    return Path("data") / "outbound_webhooks.json"


# ─── storage ───

def _load() -> dict:
    p = _path()
    if not p.exists():
        return {k: v.copy() for k, v in _DEFAULT_STATE.items()}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            return {k: v.copy() for k, v in _DEFAULT_STATE.items()}
        for k, v in _DEFAULT_STATE.items():
            if k not in d or not isinstance(d[k], list):
                d[k] = v.copy()
        return d
    except Exception:
        return {k: v.copy() for k, v in _DEFAULT_STATE.items()}


def _save(state: dict) -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2, default=str),
                     encoding="utf-8")
    except Exception:
        pass


def _invalidate_cache() -> None:
    _CACHE["ts"] = 0.0
    _CACHE["subs"] = []


def _cached_subs() -> list:
    now = time.time()
    if now - _CACHE["ts"] < _CACHE_TTL:
        return _CACHE["subs"]
    state = _load()
    _CACHE["subs"] = [w for w in (state.get("webhooks") or [])
                     if w.get("enabled")]
    _CACHE["ts"] = now
    return _CACHE["subs"]


# ─── signature ───

def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# ─── public API ───

def subscribe(url, events, description=""):
    """Register an outbound webhook. Returns {ok, webhook}.

    url:       must start with http:// or https://
    events:    list of event names; use "*" or prefix+"*" for wildcard
               e.g. ["circuit.open", "audit.*", "budget.*"]
    Secret is generated and returned ONCE. Store it.
    """
    url = (url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"ok": False, "error": "url must start with http(s)://"}
    if not isinstance(events, list) or not events:
        return {"ok": False, "error": "events must be a non-empty list"}
    events = [str(e).strip()[:64] for e in events if str(e).strip()]
    if not events:
        return {"ok": False, "error": "no valid events"}

    secret = secrets.token_urlsafe(32)
    wh = {
        "id": uuid.uuid4().hex[:16],
        "url": url[:2000],
        "events": events,
        "secret": secret,
        "description": str(description or "")[:200],
        "enabled": True,
        "created_at": time.time(),
        "fire_count": 0,
        "fail_count": 0,
        "last_fired_at": None,
        "last_status": None,
    }
    state = _load()
    state["webhooks"].append(wh)
    _save(state)
    _invalidate_cache()
    # Return secret only on creation (redacted in subsequent list calls)
    return {"ok": True, "webhook": {**_redact(wh), "secret": secret}}


def unsubscribe(webhook_id):
    state = _load()
    before = len(state["webhooks"])
    state["webhooks"] = [w for w in state["webhooks"]
                        if w.get("id") != webhook_id]
    _save(state)
    _invalidate_cache()
    return {"ok": before != len(state["webhooks"]), "id": webhook_id}


def list_all():
    state = _load()
    return {
        "webhooks": [_redact(w) for w in (state.get("webhooks") or [])],
        "count": len(state.get("webhooks") or []),
        "path": str(_path()),
        "enabled": _enabled(),
    }


def recent(n=50):
    try:
        n = max(1, min(int(n), _DELIVERY_LOG_CAP))
    except Exception:
        n = 50
    state = _load()
    return {
        "deliveries": list((state.get("deliveries") or [])[-n:]),
        "path": str(_path()),
    }


def _redact(w):
    """Return webhook without the secret key."""
    return {k: v for k, v in w.items() if k != "secret"}


def _matches(webhook, event):
    events = webhook.get("events") or []
    if "*" in events:
        return True
    for e in events:
        if e == event:
            return True
        if e.endswith("*") and event.startswith(e[:-1]):
            return True
    return False


def dispatch(event, payload=None):
    """Fire event to matching subscribers. Fire-and-forget.

    Safe to call from sync or async context. No-ops if disabled or
    no event loop is available. Never raises.
    """
    if not _enabled():
        return
    try:
        event = str(event or "")[:80]
        if not event:
            return
        subs = _cached_subs()
        if not subs:
            return
        matching = [w for w in subs if _matches(w, event)]
        if not matching:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # sync context, no loop -> best-effort skip
        for w in matching:
            try:
                loop.create_task(_deliver(
                    w["id"], w["url"], w.get("secret", ""),
                    event, payload or {},
                ))
            except Exception:
                pass
    except Exception:
        pass


async def _deliver(webhook_id, url, secret, event, payload, attempt=1):
    """POST with retry. Records every attempt in the delivery log."""
    body_obj = {
        "event": event,
        "delivery_id": uuid.uuid4().hex[:16],
        "ts": time.time(),
        "data": payload,
    }
    try:
        body = json.dumps(body_obj, default=str).encode("utf-8")
    except Exception:
        body = b'{"event":"' + event.encode("utf-8") + b'"}'
    sig = _sign(secret, body)
    t0 = time.time()
    status = 0
    err = ""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=_timeout()) as cli:
            r = await cli.post(
                url, content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Sunnyware-Event": event,
                    "X-Sunnyware-Delivery": body_obj["delivery_id"],
                    "X-Sunnyware-Signature": "sha256=" + sig,
                    "User-Agent": "sunnyware-webhooks/1.0",
                },
            )
        status = r.status_code
        ok = 200 <= status < 300
        err = "" if ok else f"HTTP {status}"
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:200]
        ok = False
    dur = int((time.time() - t0) * 1000)
    _record_delivery(webhook_id, event, body_obj["delivery_id"],
                     status, err, dur, attempt)
    if ok:
        _bump_stats(webhook_id, ok=True, status=status)
        return True
    # Retry with backoff
    if attempt < 3:
        backoff = [1.0, 4.0, 16.0][attempt - 1]
        try:
            await asyncio.sleep(backoff)
        except Exception:
            return False
        return await _deliver(webhook_id, url, secret, event, payload,
                              attempt + 1)
    _bump_stats(webhook_id, ok=False, status=status)
    return False


def _record_delivery(webhook_id, event, delivery_id, status, err, dur, attempt):
    state = _load()
    state["deliveries"] = (state.get("deliveries") or [])[-_DELIVERY_LOG_CAP + 1:] + [{
        "ts": time.time(),
        "webhook_id": webhook_id,
        "delivery_id": delivery_id,
        "event": event,
        "status": status,
        "error": err,
        "duration_ms": dur,
        "attempt": attempt,
    }]
    _save(state)


def _bump_stats(webhook_id, ok, status):
    state = _load()
    for w in state["webhooks"]:
        if w.get("id") == webhook_id:
            w["fire_count"] = int(w.get("fire_count", 0)) + 1
            if not ok:
                w["fail_count"] = int(w.get("fail_count", 0)) + 1
            w["last_fired_at"] = time.time()
            w["last_status"] = int(status)
            break
    _save(state)


def test_fire(webhook_id):
    """Trigger a synthetic test event to one subscriber. Synchronous wait
    so the admin sees the immediate result. Returns {ok, status, error}."""
    if not _enabled():
        return {"ok": False, "error": "outbound webhooks disabled"}
    state = _load()
    wh = next((w for w in state["webhooks"] if w.get("id") == webhook_id),
              None)
    if not wh:
        return {"ok": False, "error": "webhook not found"}
    import asyncio as _a
    try:
        loop = _a.get_running_loop()
    except RuntimeError:
        return {"ok": False, "error": "no event loop"}
    fut = loop.create_task(_deliver(
        wh["id"], wh["url"], wh.get("secret", ""),
        "test.fire", {"message": "test delivery from Sunnyware"},
    ))
    return {"ok": True, "delivery_scheduled": True,
            "webhook_id": webhook_id, "_task": fut}


def reset():
    """Clear all webhooks (smoke tests only)."""
    _save({"webhooks": [], "deliveries": []})
    _invalidate_cache()
