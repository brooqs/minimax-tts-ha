"""API client for the MiniMax TTS integration."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import aiohttp
from yarl import URL

from .const import (
    REQUEST_TIMEOUT,
    STATUS_AUTH_FAILED,
    STATUS_INVALID_CHARS,
    STATUS_QUOTA_EXCEEDED,
    STATUS_SUCCESS,
)
from .exceptions import (
    MiniMaxAPIError,
    MiniMaxAuthError,
    MiniMaxConnectionError,
    MiniMaxInvalidCharactersError,
    MiniMaxQuotaExceededError,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TTSRequest:
    """TTS isteği için parametre konteyneri."""

    text: str
    voice_id: str
    model: str = "speech-2.8-hd"
    speed: float = 1.0
    vol: float = 1.0
    pitch: int = 0
    emotion: str | None = None
    sample_rate: int = 32000
    bitrate: int = 128000
    language_boost: str = "auto"


@dataclass
class TTSResult:
    """TTS çağrısının sonucu."""

    audio: bytes
    audio_size: int
    audio_length_ms: int
    sample_rate: int
    bitrate: int
    word_count: int
    usage_characters: int
    elapsed_seconds: float


class MiniMaxTTSClient:
    """MiniMax T2A v2 API için async HTTP istemcisi."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.minimax.io/v1/t2a_v2",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("API key boş olamaz")
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> "MiniMaxTTSClient":
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    def _build_payload(self, req: TTSRequest) -> dict[str, Any]:
        voice_setting: dict[str, Any] = {
            "voice_id": req.voice_id,
            "speed": req.speed,
            "vol": req.vol,
            "pitch": req.pitch,
        }
        if req.emotion:
            voice_setting["emotion"] = req.emotion

        return {
            "model": req.model,
            "text": req.text,
            "stream": False,
            "language_boost": req.language_boost,
            "output_format": "hex",
            "voice_setting": voice_setting,
            "audio_setting": {
                "sample_rate": req.sample_rate,
                "bitrate": req.bitrate,
                "format": "mp3",
                "channel": 1,
            },
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "HomeAssistant-MiniMaxTTS/1.0",
        }

    async def synthesize(self, req: TTSRequest) -> TTSResult:
        if not req.text or not req.text.strip():
            raise ValueError("Text boş olamaz")
        if len(req.text) > 10000:
            raise ValueError(f"Text 10000 karakteri aşamaz (verilen: {len(req.text)})")

        session = await self._ensure_session()
        payload = self._build_payload(req)
        url = URL(self._base_url)

        t0 = time.monotonic()
        try:
            async with session.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                raw = await resp.read()

                if resp.status != 200:
                    body_text = raw.decode("utf-8", errors="replace")[:500]
                    if resp.status == 401:
                        raise MiniMaxAuthError(f"HTTP 401: {body_text}")
                    raise MiniMaxConnectionError(f"HTTP {resp.status}: {body_text}")

                try:
                    result = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as e:
                    raise MiniMaxAPIError(-1, f"Yanıt JSON değil: {e}") from e
        except asyncio.TimeoutError as e:
            raise MiniMaxConnectionError(
                f"İstek zaman aşımına uğradı ({REQUEST_TIMEOUT}s)"
            ) from e
        except aiohttp.ClientError as e:
            raise MiniMaxConnectionError(f"Ağ hatası: {e}") from e

        elapsed = time.monotonic() - t0

        base_resp = result.get("base_resp") or {}
        status_code = base_resp.get("status_code", -1)
        status_msg = base_resp.get("status_msg", "unknown")

        if status_code != STATUS_SUCCESS:
            if status_code == STATUS_AUTH_FAILED:
                raise MiniMaxAuthError(status_msg)
            if status_code == STATUS_QUOTA_EXCEEDED:
                raise MiniMaxQuotaExceededError(status_msg)
            if status_code == STATUS_INVALID_CHARS:
                raise MiniMaxInvalidCharactersError(status_msg)
            raise MiniMaxAPIError(status_code, status_msg)

        data = result.get("data") or {}
        audio_hex = data.get("audio")
        if not audio_hex:
            raise MiniMaxAPIError(-1, "Yanıtta 'audio' alanı yok")

        audio_bytes = bytes.fromhex(audio_hex)
        extra = result.get("extra_info") or {}

        return TTSResult(
            audio=audio_bytes,
            audio_size=extra.get("audio_size", len(audio_bytes)),
            audio_length_ms=extra.get("audio_length", 0),
            sample_rate=extra.get("audio_sample_rate", req.sample_rate),
            bitrate=extra.get("bitrate", req.bitrate),
            word_count=extra.get("word_count", 0),
            usage_characters=extra.get("usage_characters", len(req.text)),
            elapsed_seconds=elapsed,
        )

    async def get_voices(self) -> list[dict[str, Any]]:
        """Kullanılabilir voice listesini çek."""
        session = await self._ensure_session()
        url = URL(self._base_url.replace("/t2a_v2", "/get_voice"))
        payload = {"voice_type": "system"}

        try:
            async with session.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = (await resp.read()).decode("utf-8", errors="replace")[:300]
                    raise MiniMaxConnectionError(f"HTTP {resp.status}: {body}")
                result = await resp.json(content_type=None)
                return result.get("system_voice", [])
        except asyncio.TimeoutError as e:
            raise MiniMaxConnectionError("Voice listesi zaman aşımı") from e
        except aiohttp.ClientError as e:
            raise MiniMaxConnectionError(f"Voice listesi ağ hatası: {e}") from e
