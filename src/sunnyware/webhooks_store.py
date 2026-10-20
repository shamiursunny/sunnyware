# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 221a: Webhook endpoints + delivery log."""

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

ENDPOINTS_FILE = "webhook_endpoints.json"
DELIVERIES_FILE = "webhook_deliveries.json"
RETRIES_FILE = "webhook_retries.json"


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _load(name: str) -> dict:
    p = _base() / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(name: str, data: dict) -> bool:
    p = _base() / name
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def add_endpoint(url: str, name: str, events: list, secret: str = "") -> dict:
    endpoints = _load(ENDPOINTS_FILE)
    eid = "wh_" + secrets.token_hex(6)
    entry = {
        "id": eid,
        "url": url.strip(),
        "name": (name or "Untitled").strip()[:80],
        "events": list(events or ["*"]),
        "secret": secret or "",
        "enabled": True,
        "created_at": time.time(),
        "success_count": 0,
        "fail_count": 0,
        "last_fired": None,
    }
    endpoints[eid] = entry
    _save(ENDPOINTS_FILE, endpoints)
    return entry


def list_endpoints() -> list:
    endpoints = _load(ENDPOINTS_FILE)
    return sorted(endpoints.values(), key=lambda x: x.get("created_at", 0), reverse=True)


def delete_endpoint(eid: str) -> bool:
    endpoints = _load(ENDPOINTS_FILE)
    if eid not in endpoints:
        return False
    del endpoints[eid]
    _save(ENDPOINTS_FILE, endpoints)
    return True


def toggle_endpoint(eid: str) -> bool:
    endpoints = _load(ENDPOINTS_FILE)
    if eid not in endpoints:
        return False
    endpoints[eid]["enabled"] = not endpoints[eid].get("enabled", True)
    _save(ENDPOINTS_FILE, endpoints)
    return True


def _log_delivery(endpoint_id: str, event: str, status: str, http_status: int, body: str) -> None:
    deliveries = _load(DELIVERIES_FILE)
    did = "dlv_" + secrets.token_hex(6)
    deliveries[did] = {
        "id": did,
        "endpoint_id": endpoint_id,
        "event": event,
        "status": status,
        "http_status": http_status,
        "body": (body or "")[:500],
        "ts": time.time(),
    }
    # Keep last 1000
    if len(deliveries) > 1000:
        items = sorted(deliveries.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-1000]:
            del deliveries[k]
    _save(DELIVERIES_FILE, deliveries)


def list_deliveries(limit: int = 100) -> list:
    deliveries = _load(DELIVERIES_FILE)
    items = list(deliveries.values())
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


def clear_deliveries() -> bool:
    return _save(DELIVERIES_FILE, {})


def _attempt_delivery(ep: dict, event: str, payload: dict) -> bool:
    try:
        data = json.dumps({"event": event, "data": payload, "ts": time.time()}).encode()
        req = urllib.request.Request(ep["url"], data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Webhook-Event", event)
        if ep.get("secret"):
            req.add_header("X-Webhook-Secret", ep["secret"])
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = resp.read()[:500].decode(errors="ignore")
        _log_delivery(ep["id"], event, "delivered", status, body)
        endpoints = _load(ENDPOINTS_FILE)
        if ep["id"] in endpoints:
            endpoints[ep["id"]]["success_count"] = int(endpoints[ep["id"]].get("success_count", 0)) + 1
            endpoints[ep["id"]]["last_fired"] = time.time()
            _save(ENDPOINTS_FILE, endpoints)
        return True
    except Exception as e:
        _log_delivery(ep["id"], event, "failed", 0, str(e)[:300])
        endpoints = _load(ENDPOINTS_FILE)
        if ep["id"] in endpoints:
            endpoints[ep["id"]]["fail_count"] = int(endpoints[ep["id"]].get("fail_count", 0)) + 1
            endpoints[ep["id"]]["last_fired"] = time.time()
            _save(ENDPOINTS_FILE, endpoints)
        return False


def _deliver(ep: dict, event: str, payload: dict, retries: int = 0) -> None:
    success = _attempt_delivery(ep, event, payload)
    if not success:
        _add_retry(ep, event, payload, 0)




def _add_retry(endpoint: dict, event: str, payload: dict, attempt: int):
    retries = _load(RETRIES_FILE)
    rid = "rty_" + secrets.token_hex(6)
    # 1m, 5m, 30m, 2h
    delays = [60, 300, 1800, 7200]
    delay = delays[attempt] if attempt < len(delays) else 7200
    retries[rid] = {
        "id": rid,
        "endpoint": endpoint,
        "event": event,
        "payload": payload,
        "attempt": attempt,
        "next_retry": time.time() + delay
    }
    _save(RETRIES_FILE, retries)


def process_retries():
    """Called by the background worker to process pending retries."""
    retries = _load(RETRIES_FILE)
    now = time.time()
    pending = [r for r in retries.values() if r.get("next_retry", 0) <= now]
    
    if not pending:
        return

    for r in pending:
        rid = r["id"]
        ep = r["endpoint"]
        event = r["event"]
        payload = r["payload"]
        attempt = r.get("attempt", 0)

        # Attempt delivery
        success = _attempt_delivery(ep, event, payload)
        
        if success:
            del retries[rid]
        else:
            if attempt >= 3:  # 4 attempts total (0,1,2,3)
                _log_delivery(ep["id"], event, "failed_permanently", 0, "Retries exhausted")
                del retries[rid]
            else:
                # Schedule next retry
                delays = [60, 300, 1800, 7200]
                delay = delays[attempt + 1] if (attempt + 1) < len(delays) else 7200
                retries[rid]["attempt"] = attempt + 1
                retries[rid]["next_retry"] = time.time() + delay
    _save(RETRIES_FILE, retries)

def fire_event(event_type: str, payload: dict, retries: int = 3) -> int:
    """Fire webhooks for the event type. Returns number of endpoints fired."""
    endpoints = _load(ENDPOINTS_FILE)
    fired = 0
    for eid, ep in endpoints.items():
        if not ep.get("enabled"):
            continue
        subscribed = ep.get("events", [])
        if "*" not in subscribed and event_type not in subscribed:
            continue
        threading.Thread(target=_deliver, args=(ep, event_type, payload, retries), daemon=True).start()
        fired += 1
    return fired
