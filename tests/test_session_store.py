import pytest
from backend.storage.redis_session import RedisSessionStore

@pytest.mark.asyncio
async def test_session_store_local_caching_and_turn_windowing():
    session_store = RedisSessionStore()
    session_id = "test_sess_123"

    # Test initial default session retrieval
    session = await session_store.get_session(session_id)
    assert session["session_id"] == session_id
    assert session["state"] == "idle"
    assert len(session["last_turns"]) == 0

    # Test state update
    updated = await session_store.set_state(session_id, "listening")
    assert updated["state"] == "listening"

    # Test turn addition and sliding window (max 6 turns)
    for i in range(10):
        role = "user" if i % 2 == 0 else "assistant"
        await session_store.add_turn(session_id, role, f"Message {i}")

    session = await session_store.get_session(session_id)
    assert len(session["last_turns"]) == 6
    assert session["last_turns"][-1]["text"] == "Message 9"
