import logging
import httpx
from typing import Optional
from backend.config import settings

logger = logging.getLogger("voxassist.tts")

class RimeTTSClient:
    """
    Rime TTS Engine client. Synthesizes complete audio for a line of text —
    the browser plays the real returned audio (no fabricated chunks/amplitude).
    """
    def __init__(self):
        self.api_key = settings.RIME_API_KEY
        self.voice_id = settings.RIME_VOICE_ID
        self.speed_alpha = settings.RIME_SPEAKER_SPEED
        self.is_live = settings.is_rime_live

    async def synthesize_speech(self, text: str) -> Optional[bytes]:
        """
        Returns complete MP3 audio bytes from Rime, or None if Rime is not
        configured or the request fails (caller should fall back to another
        voice — e.g. Rime does not speak every language the app supports).
        """
        if not self.is_live:
            return None

        try:
            url = "https://users.rime.ai/v1/rime-tts"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "audio/mp3"
            }
            payload = {
                "speaker": self.voice_id,
                "text": text,
                "modelId": "v1",
                "samplingRate": 22050,
                "speedAlpha": self.speed_alpha
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=15.0)
                if response.status_code == 200:
                    return response.content
                logger.error(f"Rime API Error Status {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.error(f"Rime TTS synthesis error: {e}")

        return None

rime_tts = RimeTTSClient()
