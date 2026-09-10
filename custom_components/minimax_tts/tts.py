"""TTS platform for MiniMax TTS integration."""
from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url

from .const import (
    CONF_BITRATE,
    CONF_EMOTION,
    CONF_LANGUAGE_BOOST,
    CONF_MODEL,
    CONF_PITCH,
    CONF_SAMPLE_RATE,
    CONF_SPEED,
    CONF_VOICE_ID,
    CONF_VOLUME,
    DEFAULT_BITRATE,
    DEFAULT_LANGUAGE_BOOST,
    DEFAULT_MODEL,
    DEFAULT_PITCH,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SPEED,
    DEFAULT_VOICE_ID,
    DEFAULT_VOLUME,
    DOMAIN,
    MAX_TEXT_LENGTH,
)
from .coordinator import MiniMaxTTSClient, TTSRequest
from .exceptions import MiniMaxTTSError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config entry'den TTS entity'si oluştur."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: MiniMaxTTSClient = data["client"]
    config_entry_obj = data["entry"]

    async_add_entities(
        [MiniMaxTTSEntity(hass, config_entry_obj, client)], update_before_add=True
    )


class MiniMaxTTSEntity(TextToSpeechEntity):
    """MiniMax TTS entity'si."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MiniMaxTTSClient,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._client = client
        self._cache_dir = Path(hass.config.path("www")) / "minimax_tts"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_tts"

    @property
    def default_language(self) -> str:
        return "tr"

    @property
    def supported_languages(self) -> list[str]:
        return ["tr", "en"]

    @property
    def supported_options(self) -> list[str]:
        return [
            CONF_VOICE_ID,
            CONF_MODEL,
            CONF_SPEED,
            CONF_PITCH,
            CONF_EMOTION,
            CONF_VOLUME,
            CONF_LANGUAGE_BOOST,
        ]

    def _resolve_options(self, options: dict[str, Any]) -> dict[str, Any]:
        merged = {
            CONF_VOICE_ID: DEFAULT_VOICE_ID,
            CONF_MODEL: DEFAULT_MODEL,
            CONF_SPEED: DEFAULT_SPEED,
            CONF_PITCH: DEFAULT_PITCH,
            CONF_VOLUME: DEFAULT_VOLUME,
            CONF_LANGUAGE_BOOST: DEFAULT_LANGUAGE_BOOST,
            CONF_SAMPLE_RATE: DEFAULT_SAMPLE_RATE,
            CONF_BITRATE: DEFAULT_BITRATE,
        }
        for key, val in self._entry.options.items():
            if key in merged:
                merged[key] = val
        for key, val in (options or {}).items():
            if key in merged:
                merged[key] = val
        return merged

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        if not message or not message.strip():
            return ("audio/mpeg", b"")

        if len(message) > MAX_TEXT_LENGTH:
            _LOGGER.warning(
                "Mesaj %d karakter > %d, kesilecek",
                len(message),
                MAX_TEXT_LENGTH,
            )
            message = message[:MAX_TEXT_LENGTH]

        opts = self._resolve_options(options or {})
        if opts.get(CONF_LANGUAGE_BOOST) == "auto" and language:
            lang_map = {"tr": "Turkish", "en": "English", "zh": "Chinese"}
            if language in lang_map:
                opts[CONF_LANGUAGE_BOOST] = lang_map[language]

        req = TTSRequest(
            text=message,
            voice_id=opts[CONF_VOICE_ID],
            model=opts[CONF_MODEL],
            speed=opts[CONF_SPEED],
            vol=opts.get(CONF_VOLUME, DEFAULT_VOLUME),
            pitch=opts[CONF_PITCH],
            emotion=opts.get(CONF_EMOTION) or None,
            sample_rate=opts[CONF_SAMPLE_RATE],
            bitrate=opts[CONF_BITRATE],
            language_boost=opts[CONF_LANGUAGE_BOOST],
        )

        try:
            result = await self._client.synthesize(req)
        except MiniMaxTTSError as err:
            _LOGGER.error("MiniMax TTS hatası: %s", err)
            return ("audio/mpeg", b"")
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Beklenmeyen TTS hatası: %s", err)
            return ("audio/mpeg", b"")

        filename = f"{secrets.token_hex(8)}.mp3"
        filepath = self._cache_dir / filename
        try:
            filepath.write_bytes(result.audio)
        except OSError as err:
            _LOGGER.error("Cache yazma hatası: %s", err)
            return ("audio/mpeg", result.audio)

        try:
            base = get_url(self.hass, prefer_external=True)
            url = f"{base}/local/minimax_tts/{filename}"
        except Exception:  # noqa: BLE001
            url = f"/local/minimax_tts/{filename}"

        _LOGGER.debug(
            "MiniMax TTS: %s -> %s (%d bytes)",
            req.voice_id,
            url,
            result.audio_size,
        )

        return ("audio/mpeg", url)
