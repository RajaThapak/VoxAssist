import pytest
import json
import websockets

WS_URI = "ws://localhost:8000/ws/voxassist"

@pytest.mark.asyncio
async def test_websocket_voice_flow_turn():
    async with websockets.connect(WS_URI) as ws:
        # Handshake
        conn_raw = await ws.recv()
        conn_data = json.loads(conn_raw)
        assert conn_data.get("type") == "connected"
        assert len(conn_data.get("session_id", "")) > 0

        # Turn 1
        await ws.send(json.dumps({
            "type": "user_speech",
            "text": "My Wi-Fi keeps disconnecting during video calls"
        }))

        got_speaking = False
        got_audio_segment = False

        while True:
            msg_raw = await ws.recv()
            event = json.loads(msg_raw)
            event_type = event.get("type")

            if event_type == "state_change" and event.get("state") == "speaking":
                got_speaking = True
            elif event_type in ("tts_audio_segment", "tts_text_segment"):
                got_audio_segment = True
            elif event_type == "tts_stream_end":
                break

        assert got_speaking is True
        assert got_audio_segment is True
