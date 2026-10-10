# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Memory / event log via Neon (append-only events table)."""

import json
import re
from typing import Optional
from . import state as app_state


# ── Part 31E: memory payload caps (protects Groq 8K TPM budget) ──
MAX_LOG_CONTENT_CHARS = 2000        # cap at write time
MAX_HISTORY_CONTENT_CHARS = 800     # cap at read time (build_context)
MAX_CONTEXT_CONTENT_CHARS = 200     # cap for cross-session context
# Base64 heuristic: long run with MIXED char classes (uppercase + lowercase + digit
# OR +/= padding). Pure-lowercase/uppercase runs (e.g. "xxxxxx") are NOT redacted
# because they're common in legitimate text and hash prefixes.
_BASE64_MARKER = re.compile(
    r"(?=[A-Za-z0-9+/]*[A-Z])"        # has uppercase
    r"(?=[A-Za-z0-9+/]*[a-z])"        # has lowercase
    r"(?=[A-Za-z0-9+/]*[0-9])"        # has digit
    r"[A-Za-z0-9+/]{500,}={0,2}"      # 500+ base64-ish chars
)


def _sanitize_content(text: str, max_chars: int) -> str:
    """Truncate text and redact embedded base64 blobs.

    Base64 images from python_eval were the primary cause of Groq 413s.
    Replace any 500+ char alphanumeric+/= run with a short marker.
    """
    if not text:
        return ""
    text = str(text)
    # Redact long base64-like runs
    def _repl(m):
        return "[redacted: " + str(len(m.group(0))) + " bytes]"
    text = _BASE64_MARKER.sub(_repl, text)
    # Truncate to cap
    if len(text) > max_chars:
        text = text[:max_chars] + "... [truncated, orig " + str(len(text)) + " chars]"
    return text


async def log_event(
    session_uuid: str, event_type: str, payload: Optional[dict] = None
) -> Optional[int]:
    """Append event. Returns event id, or None if DB unavailable.

    Silently no-ops when DB/pool unavailable — never fails the request path.
    """
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return None
    # Part 31E: sanitize before writing — prevents token blowup on replay
    clean_payload = dict(payload or {})
    if "content" in clean_payload:
        clean_payload["content"] = _sanitize_content(
            clean_payload.get("content", ""), MAX_LOG_CONTENT_CHARS
        )
    try:
        async with pool.acquire() as conn:
            event_id = await conn.fetchval(
                """
                INSERT INTO events (session_id, event_type, payload)
                VALUES ($1::uuid, $2, $3::jsonb)
                RETURNING id
                """,
                session_uuid, event_type, json.dumps(clean_payload),
            )
            return event_id
    except Exception:
        return None


async def get_history(session_uuid: str, limit: int = 50) -> list:
    """Get recent events for a session (oldest first)."""
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, event_type, payload, created_at
                FROM events
                WHERE session_id = $1::uuid
                ORDER BY id DESC
                LIMIT $2
                """,
                session_uuid, limit,
            )
            return [
                {
                    "id": r["id"],
                    "event_type": r["event_type"],
                    "payload": r["payload"],
                    "created_at": r["created_at"].isoformat(),
                }
                for r in reversed(rows)
            ]
    except Exception:
        return []


async def count_events(session_uuid: str) -> int:
    """Count events for a session."""
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return 0
    try:
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM events WHERE session_id = $1::uuid",
                session_uuid,
            ) or 0
    except Exception:
        return 0


def _extract_content(payload) -> str:
    """Extract 'content' from payload (JSONB may arrive as str or dict)."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return ""
    if isinstance(payload, dict):
        return payload.get("content", "") or ""
    return ""


async def build_context(session_uuid: str, max_turns: int = 6) -> list:
    """Build OpenAI-format messages array from session history.

    Returns list of {role, content} dicts in chronological order.
    Only includes user_message and assistant_message events.
    Caps at max_turns turns (2 events per turn).
    """
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT event_type, payload
                FROM events
                WHERE session_id = $1::uuid
                  AND event_type IN ('user_message', 'assistant_message')
                ORDER BY id DESC
                LIMIT $2
                """,
                session_uuid, max_turns * 2,
            )
        messages = []
        for r in reversed(rows):
            content = _extract_content(r["payload"])
            if not content:
                continue
            # Part 31E: cap replay size — belt & suspenders
            content = _sanitize_content(content, MAX_HISTORY_CONTENT_CHARS)
            if r["event_type"] == "user_message":
                messages.append({"role": "user", "content": content})
            elif r["event_type"] == "assistant_message":
                messages.append({"role": "assistant", "content": content})
        return messages
    except Exception:
        return []


# ── Part 8: cross-session memory selection ──────────────────────────────────

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "what", "who", "when", "where", "how", "why", "which",
    "my", "your", "our", "their", "his", "her", "its",
    "and", "or", "but", "of", "in", "on", "at", "to", "for", "with", "from",
    "by", "as", "into", "about", "over", "under",
    "it", "this", "that", "these", "those",
    "have", "has", "had", "do", "does", "did",
    "you", "me", "we", "us", "them", "they", "i",
    "will", "would", "could", "should", "can", "may", "might",
    "please", "just", "only", "also", "very", "really",
}


def _extract_keywords(query: str, max_keywords: int = 5) -> list:
    """Extract candidate keywords from user query (lowercase, len>=4)."""
    import re
    tokens = re.findall(r"[a-zA-Z0-9]{4,}", query.lower())
    # Preserve order, dedupe
    seen = set()
    out = []
    for t in tokens:
        if t in _STOPWORDS or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= max_keywords:
            break
    return out


async def select_relevant_events(
    query: str,
    exclude_session_uuid: Optional[str] = None,
    limit: int = 3,
) -> list:
    """Select relevant past events from OTHER sessions matching query keywords.

    Strategy:
      1. Extract keywords from query
      2. SQL: fetch recent events matching ANY keyword (ILIKE)
      3. Exclude current session (multi-turn already has that)
      4. Score by keyword match count + recency
      5. Return top-N
    """
    pool = app_state.get_pool()
    if pool is None or not query:
        return []

    keywords = _extract_keywords(query)
    if not keywords:
        return []

    patterns = [f"%{k}%" for k in keywords]

    # Part 24: scope to current tenant
    try:
        from . import tenant as _tenant
        owner = _tenant.get_key()
    except Exception:
        owner = ""

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT e.id, e.event_type, e.payload, e.created_at,
                       s.session_key, s.id AS session_uuid
                FROM events e
                JOIN sessions s ON s.id = e.session_id
                WHERE e.event_type IN ('user_message', 'assistant_message')
                  AND e.payload::text ILIKE ANY($1::text[])
                  AND ($2::uuid IS NULL OR e.session_id != $2::uuid)
                  AND s.owner_key = $3
                ORDER BY e.id DESC
                LIMIT 30
                """,
                patterns,
                exclude_session_uuid,
                owner,
            )
    except Exception:
        return []

    # Score: keyword hit count (desc), then recency (desc by id)
    scored = []
    for r in rows:
        text = str(r["payload"]).lower()
        score = sum(1 for k in keywords if k in text)
        scored.append((score, r["id"], r))

    scored.sort(key=lambda x: (-x[0], -x[1]))

    return [
        {
            "id": r["id"],
            "event_type": r["event_type"],
            "payload": r["payload"],
            "session_key": r["session_key"],
            "created_at": r["created_at"].isoformat(),
        }
        for _score, _id, r in scored[:limit]
    ]


def format_context(events: list, max_chars_per_event: int = 200) -> str:
    """Format selected events as a plain text context block for LLM."""
    if not events:
        return ""
    lines = []
    for ev in events:
        payload = ev.get("payload", {})
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        content = payload.get("content", "") if isinstance(payload, dict) else ""
        if not content:
            continue
        content = _sanitize_content(str(content), max_chars_per_event)
        content = content.replace("\n", " ").strip()
        role = "user" if ev.get("event_type") == "user_message" else "assistant"
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


# ── Part 9: session history helpers ─────────────────────────────────────────

async def get_all_events(session_uuid: str, max_limit: int = 1000) -> list:
    """Get ALL events for a session, oldest first. Capped at max_limit."""
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, event_type, payload, created_at
                FROM events
                WHERE session_id = $1::uuid
                ORDER BY id ASC
                LIMIT $2
                """,
                session_uuid, max_limit,
            )
        return [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "payload": r["payload"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    except Exception:
        return []


async def delete_events_after(session_uuid: str, event_id: int) -> int:
    """Delete all events with id > event_id for this session. Returns count deleted."""
    pool = app_state.get_pool()
    if pool is None or not session_uuid:
        return 0
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM events WHERE session_id = $1::uuid AND id > $2",
                session_uuid, event_id,
            )
            # asyncpg returns "DELETE N"
            parts = result.split()
            return int(parts[1]) if len(parts) == 2 else 0
    except Exception:
        return 0


async def health_check() -> dict:
    """Verify events table accessible."""
    pool = app_state.get_pool()
    if pool is None:
        return {"status": "no_pool"}
    try:
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM events")
            return {"status": "ok", "count": count}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
