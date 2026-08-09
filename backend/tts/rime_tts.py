import time
import logging
import httpx
from typing import Optional
from backend.config import settings

logger = logging.getLogger("voxassist.tts")

class RimeTTSClient:
    """
    Rime TTS Engine client. Synthesizes complete audio for a line of text —
    the browser plays the real returned audio (no fabricated chunks/amplitude).

    Uses a single persistent, connection-pooled AsyncClient (module lifetime)
    instead of opening a fresh TCP+TLS connection to users.rime.ai on every
    call — that handshake was previously paid on every single TTS request.
    """
    def __init__(self):
        self.api_key = settings.RIME_API_KEY
        self.voice_id = settings.RIME_VOICE_ID
        self.speed_alpha = settings.RIME_SPEAKER_SPEED
        self.is_live = settings.is_rime_live
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                limits=httpx.Limits(max_keepalive_connections=10, keepalive_expiry=60.0),
            )
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def synthesize_speech(self, text: str) -> Optional[bytes]:
        """
        Returns complete MP3 audio bytes from Rime, or None if Rime is not
        configured or the request fails (caller should fall back to another
        voice — e.g. Rime does not speak every language the app supports).
        """
        if not self.is_live:
            return None

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

        client = self._get_client()
        started = time.monotonic()
        try:
            # Stream the response instead of forcing httpx to buffer the full
            # body before returning, so bytes are consumed as they arrive
            # rather than only after the entire clip is generated server-side.
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                headers_at_ms = (time.monotonic() - started) * 1000
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error(f"Rime API Error Status {response.status_code}: {body[:200]}")
                    return None
                chunks = []
                first_byte_ms = None
                async for chunk in response.aiter_bytes():
                    if first_byte_ms is None:
                        first_byte_ms = (time.monotonic() - started) * 1000
                    chunks.append(chunk)
            audio_bytes = b"".join(chunks)
            elapsed_ms = (time.monotonic() - started) * 1000
            logger.info(
                f"[latency] Rime synthesis: request_sent->headers={headers_at_ms:.0f}ms "
                f"request_sent->first_byte={(first_byte_ms or elapsed_ms):.0f}ms "
                f"request_sent->last_byte(total)={elapsed_ms:.0f}ms "
                f"for {len(text)} chars -> {len(audio_bytes)} bytes"
            )
            return audio_bytes
        except Exception as e:
            logger.error(f"Rime TTS synthesis error: {e}")

        return None

rime_tts = RimeTTSClient()
