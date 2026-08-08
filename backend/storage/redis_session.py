import json
import logging
from typing import Dict, Any, List, Optional
import redis.asyncio as aioredis
from backend.config import settings

logger = logging.getLogger("voxassist.redis")

class RedisSessionStore:
    """
    Manages live session state, short-term conversational turns, and barge-in signaling.
    Includes in-memory fallback if Redis connection is unavailable.
    """
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self.use_redis: bool = False

    async def connect(self):
        try:
            self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
            await self.redis.ping()
            self.use_redis = True
            logger.info("Connected to Redis successfully.")
        except Exception as e:
            logger.warning(f"Redis connection unavailable ({e}). Using in-memory session store fallback.")
            self.use_redis = False

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        if self.use_redis and self.redis:
            try:
                data = await self.redis.get(f"session:{session_id}")
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Error fetching from Redis: {e}")
        
        return self._local_cache.get(session_id, {
            "state": "idle",
            "last_turns": [],
            "device_context": "Windows 11, Corporate Workstation",
            "current_kb_id": None,
            "current_step_index": 0,
            "ticket_draft": None
        })

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        session = await self.get_session(session_id)
        session.update(updates)
        
        if self.use_redis and self.redis:
            try:
                await self.redis.setex(f"session:{session_id}", 3600, json.dumps(session))
            except Exception as e:
                logger.error(f"Error updating Redis: {e}")
        
        self._local_cache[session_id] = session
        return session

    async def set_state(self, session_id: str, state: str) -> Dict[str, Any]:
        """Valid states: idle | listening | thinking | speaking | interrupted | escalating"""
        return await self.update_session(session_id, {"state": state})

    async def add_turn(self, session_id: str, role: str, text: str) -> Dict[str, Any]:
        session = await self.get_session(session_id)
        turns = session.get("last_turns", [])
        turns.append({"role": role, "text": text})
        if len(turns) > 10:
            turns = turns[-10:]
        return await self.update_session(session_id, {"last_turns": turns})

    async def publish_interrupt(self, session_id: str):
        """Publishes barge-in interrupt signal for real-time stream cancellation"""
        if self.use_redis and self.redis:
            try:
                await self.redis.publish(f"interrupt:{session_id}", "BargeIn")
            except Exception as e:
                logger.error(f"Failed to publish interrupt to Redis: {e}")

session_store = RedisSessionStore()
