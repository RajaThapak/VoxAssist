import json
import logging
from typing import Dict, Any, List
from backend.storage.mongo_db import mongo_store

logger = logging.getLogger("voxassist.tools")

CREATE_TICKET_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "create_ticket",
        "description": "Escalates an unresolved IT issue to a human support technician by opening a high-priority ticket.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_summary": {
                    "type": "string",
                    "description": "Concise 1-sentence summary of the IT problem reported by the user."
                },
                "steps_tried": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of troubleshooting steps already attempted during this session."
                },
                "transcript_summary": {
                    "type": "string",
                    "description": "Short recap of the conversation leading up to escalation."
                }
            },
            "required": ["issue_summary", "steps_tried", "transcript_summary"]
        }
    }
}

END_SESSION_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "end_session",
        "description": "Ends the voice support session after the user confirms their issue is resolved and they have nothing else they need help with.",
        "parameters": {
            "type": "object",
            "properties": {
                "farewell_message": {
                    "type": "string",
                    "description": "A short, warm, natural closing line to speak before ending the session. Vary the wording each time — never reuse the same phrase turn to turn."
                }
            },
            "required": ["farewell_message"]
        }
    }
}

async def execute_create_ticket(session_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    issue_summary = arguments.get("issue_summary", "IT Support Assistance Required")
    steps_tried = arguments.get("steps_tried", [])
    transcript_summary = arguments.get("transcript_summary", "")

    ticket = mongo_store.create_ticket(
        session_id=session_id,
        issue_summary=issue_summary,
        steps_tried=steps_tried,
        transcript_summary=transcript_summary
    )
    
    return {
        "status": "success",
        "message": f"Escalation ticket {ticket['ticket_id']} has been created successfully.",
        "ticket": ticket
    }
