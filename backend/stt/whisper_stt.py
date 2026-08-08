import io
import logging
from typing import Optional
from openai import AsyncOpenAI
from backend.config import settings

logger = logging.getLogger("voxassist.stt")

class WhisperSTT:
    """
    Speech-To-Text transcriber via OpenAI Whisper API or client transcript forwarding.
    """
    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None
        if settings.is_openai_live:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def transcribe_audio_bytes(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        if self.client:
            try:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = filename
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
                return transcript.text.strip()
            except Exception as e:
                logger.error(f"Whisper STT Error: {e}")
        
        return ""

stt_engine = WhisperSTT()
