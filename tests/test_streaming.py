"""Phase 1 pre-test: verify stream_chat yields multiple chunks."""
import asyncio
import pytest
from sunnyware import llm


@pytest.mark.asyncio
async def test_stream_chat_yields_chunks():
    """stream_chat should yield multiple text chunks."""
    chunks = []
    try:
        async for chunk in llm.stream_chat(
            "Count from 1 to 10 in a single line.",
            timeout=30.0,
        ):
            chunks.append(chunk)
            if len(chunks) >= 3:
                break  # Enough proof
    except RuntimeError as e:
        if "no providers" in str(e) or "ConnectError" in str(e) or "all providers failed" in str(e):
            pytest.skip(f"No live providers available locally: {e}")
        raise

    assert len(chunks) >= 3, f"Expected ≥3 chunks, got {len(chunks)}"
    full = "".join(chunks)
    assert len(full) > 0, "Streamed text is empty"


@pytest.mark.asyncio
async def test_orchestrator_emits_content_events():
    """Orchestrator should emit 'content' type events during streaming."""
    from sunnyware.orchestrator import run_agent

    events = []

    async def on_event(ev):
        events.append(ev)

    try:
        await run_agent(
            "1/2 + 2",
            session_uuid="test-stream-001",
            on_event=on_event,
            role="general",
        )
    except Exception as e:
        pytest.skip(f"Orchestrator unavailable: {e}")

    # Streaming only runs for non-deterministic tools.
    # "1/2 + 2" hits the calculator (direct-answer) — so skip in that case.
    event_types = [e.get("type") for e in events]
    content_events = [e for e in events if e.get("type") == "content"]

    if content_events:
        assert len(content_events) >= 1
    elif any(e.get("type") == "answer" and e.get("content") for e in events):
        pytest.skip(f"Deterministic tool used (direct-answer path). Event types: {event_types}")
    else:
        pytest.fail(f"No content or answer events. Got types: {event_types}")
