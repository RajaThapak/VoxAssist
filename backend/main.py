import asyncio
import os
import json
import base64
import random
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.storage.redis_session import session_store
from backend.storage.mongo_db import mongo_store
from backend.rag.qdrant_kb import qdrant_manager
from backend.tts.rime_tts import rime_tts
from backend.agent.orchestrator import AgentOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("voxassist.main")

GREETINGS = [
    "Hi Alex! I'm VoxAssist, your IT Helpdesk agent. What issue are you running into today?",
    "Hello Alex, VoxAssist here. What tech trouble can I help you fix today?",
    "Hey Alex! This is VoxAssist — tell me what's going on and I'll help you sort it out.",
    "Welcome back, Alex. I'm VoxAssist, ready to help with your IT issue today.",
    "Hi there, VoxAssist speaking. What can I help you troubleshoot today?"
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Initializing VoxAssist backend services...")
    await session_store.connect()
    mongo_store.connect()
    await qdrant_manager.init_db()
    yield
    logger.info("VoxAssist backend shut down.")

app = FastAPI(title="VoxAssist API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST Endpoints
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "VoxAssist Voice Helpdesk",
        "redis": session_store.use_redis,
        "mongo": mongo_store.use_mongo,
        "qdrant": qdrant_manager.use_qdrant,
        "openai_live": settings.is_openai_live,
        "rime_live": settings.is_rime_live
    }

@app.get("/api/kb")
async def list_kb():
    return {"articles": await qdrant_manager.search_kb("", limit=20)}

@app.get("/api/tickets")
async def list_tickets():
    return {"tickets": mongo_store.list_tickets()}

# WebSocket Real-Time Voice Endpoint
@app.websocket("/ws/voxassist")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = f"sess_{os.urandom(4).hex()}"
    logger.info(f"New WebSocket client connected: {session_id}")

    async def send_ws_event(event: dict):
        try:
            await websocket.send_text(json.dumps(event))
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")

    orchestrator = AgentOrchestrator(session_id, send_ws_event)
    await session_store.set_state(session_id, "listening")

    greeting_text = random.choice(GREETINGS)
    greeting_audio = await rime_tts.synthesize_speech(greeting_text)
    connected_event = {
        "type": "connected",
        "session_id": session_id,
        "state": "listening",
        "greeting": greeting_text
    }
    if greeting_audio:
        connected_event["audio_base64"] = base64.b64encode(greeting_audio).decode("ascii")
        connected_event["mime"] = "audio/mp3"
    await send_ws_event(connected_event)

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")

            if msg_type == "barge_in":
                # Instant interruption signal from frontend
                await orchestrator.interrupt_controller.trigger_barge_in()
                await send_ws_event({"type": "state_change", "state": "interrupted"})

            elif msg_type == "user_speech":
                text = data.get("text", "").strip()
                if text:
                    task = asyncio.create_task(orchestrator.process_user_turn(text))
                    orchestrator.interrupt_controller.register_tasks(llm_task=task)

            elif msg_type == "ping":
                await send_ws_event({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in {session_id}: {e}")

# Mount static frontend
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=False)
