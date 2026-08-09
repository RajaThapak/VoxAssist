import pytest
from backend.agent.tools import execute_create_ticket
from backend.storage.redis_session import session_store
from backend.storage.mongo_db import mongo_store

@pytest.mark.asyncio
async def test_ticket_creation_idempotency():
    session_id = "test_ticket_idempotency_session"
    
    # First call to create ticket
    res1 = await execute_create_ticket(session_id, {
        "issue_summary": "VPN connection issue",
        "steps_tried": ["Restarted VPN client"],
        "transcript_summary": "User needs VPN escalation"
    })
    ticket1_id = res1["ticket"]["ticket_id"]

    # Second call to create ticket for SAME session
    res2 = await execute_create_ticket(session_id, {
        "issue_summary": "VPN connection issue",
        "steps_tried": ["Restarted VPN client"],
        "transcript_summary": "User needs VPN escalation"
    })
    ticket2_id = res2["ticket"]["ticket_id"]

    # Must return exact same ticket ID (no duplicate created)
    assert ticket1_id == ticket2_id
    assert res2["message"] == f"Escalation ticket {ticket1_id} is already open."
