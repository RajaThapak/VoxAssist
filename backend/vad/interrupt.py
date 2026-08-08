import logging
import asyncio
from typing import Optional, Callable
from backend.storage.redis_session import session_store

logger = logging.getLogger("voxassist.vad")

class InterruptController:
    """
    Handles user barge-in detection and task cancellation.
    Target interruption latency: < 300ms.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.active_llm_task: Optional[asyncio.Task] = None
        self.active_tts_task: Optional[asyncio.Task] = None

    def register_tasks(self, llm_task: Optional[asyncio.Task] = None, tts_task: Optional[asyncio.Task] = None):
        self.active_llm_task = llm_task
        self.active_tts_task = tts_task

    async def trigger_barge_in(self) -> bool:
        """
        Immediately cancels active LLM text generation and Rime TTS streams.
        Updates session state to 'interrupted'.
        """
        logger.info(f"⚡ BARGE-IN DETECTED for session {self.session_id}! Cancelling streams...")
        
        cancelled = False
        if self.active_llm_task and not self.active_llm_task.done():
            self.active_llm_task.cancel()
            cancelled = True
            
        if self.active_tts_task and not self.active_tts_task.done():
            self.active_tts_task.cancel()
            cancelled = True

        await session_store.set_state(self.session_id, "interrupted")
        await session_store.publish_interrupt(self.session_id)
        return cancelled
