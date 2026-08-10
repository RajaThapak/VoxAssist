import pytest
from fastapi.testclient import TestClient
from backend.main import app

def test_websocket_voice_flow_turn():
    client = TestClient(app)
    with client.websocket_connect("/ws/voxassist") as ws:
        # Handshake
        conn_data = ws.receive_json()
        assert conn_data.get("type") == "connected"
        assert len(conn_data.get("session_id", "")) > 0

        # Turn 1
        ws.send_json({
            "type": "user_speech",
            "text": "My Wi-Fi keeps disconnecting during video calls"
        })

        got_speaking = False
        got_audio_segment = False

        while True:
            event = ws.receive_json()
            event_type = event.get("type")

            if event_type == "state_change" and event.get("state") == "speaking":
                got_speaking = True
            elif event_type in ("tts_audio_segment", "tts_text_segment"):
                got_audio_segment = True
            elif event_type == "tts_stream_end":
                break

        assert got_speaking is True
        assert got_audio_segment is True
