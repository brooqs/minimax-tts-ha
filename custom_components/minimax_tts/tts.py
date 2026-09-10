"""TTS platform for MiniMax TTS integration.

Implements both legacy config_yaml-style (async_get_engine -> Provider)
and modern config_entry-style (async_setup_entry -> Provider per entry).

Pattern modeled after HA Core's google_cloud/tts.py.
"""
from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.tts import (
    CONF_LANG,
    Provider,
    TextToSpeechEntity,
    TtsAudioType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import get_url

from .const import (
    AVAILABLE_EMOTIONS,
    AVAILABLE_LANGUAGE_BOOSTS,
    AVAILABLE_MODELS,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_BITRATE,
    CONF_EMOTION,
    CONF_LANGUAGE_BOOST,
    CONF_MODEL,
    CONF_PITCH,
    CONF_SAMPLE_RATE,
    CONF_SPEED,
    CONF_VOICE_ID,
    CONF_VOLUME,
    DEFAULT_BASE_URL,
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

_LOGGER = logging.getLogger(__name__)

# Per-language defaults — MiniMax can detect language from text, but we
# forward an explicit language_boost when caller provides a lang code.
_LANG_MAP = {
    "tr": "Turkish",
    "en": "English",
    "en-US": "English",
    "en-GB": "English",
    "zh": "Chinese",
    "zh-CN": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "ru": "Russian",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
}


# =========================================================================
# Legacy YAML entry-point (still required for backwards compatibility)
# =========================================================================


async def async_get_engine(
    hass: HomeAssistant,
    config: dict[str, Any],
    discovery_info: dict[str, Any] | None = None,
) -> Provider | None:
    """Set up MiniMax TTS provider from YAML config (legacy)."""
    api_key = config.get(CONF_API_KEY)
    base_url = config.get(CONF_BASE_URL, DEFAULT_BASE_URL)
    if not api_key:
        _LOGGER.error("API key required in YAML configuration")
        return None

    client = MiniMaxTTSClient(api_key=api_key, base_url=base_url)
    # Open the client session now — Provider has no async setup hook
    await client.__aenter__()
    return MiniMaxProvider(hass, client, None)


# =========================================================================
# Modern config_entry entry-point
# =========================================================================


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MiniMax TTS from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: MiniMaxTTSClient = data["client"]

    async_add_entities(
        [MiniMaxProvider(hass, client, config_entry)], update_before_add=True
    )


# =========================================================================
# Provider implementation
# =========================================================================


class MiniMaxProvider(Provider):
    """MiniMax TTS provider."""

    # Provider name shown in HA UI / used as engine_id
    name = "MiniMax TTS"

    def __init__(
        self,
        hass: HomeAssistant,
        client: MiniMaxTTSClient,
        entry: ConfigEntry | None,
    ) -> None:
        """Initialize the provider."""
        self.hass = hass
        self._client = client
        self._entry = entry

        # Per-call mutable state (HA's TTS pipeline resets between calls)
        self._language: str = "tr"
        self._voice_id: str = DEFAULT_VOICE_ID
        self._model: str = DEFAULT_MODEL
        self._speed: float = DEFAULT_SPEED
        self._pitch: int = DEFAULT_PITCH
        self._emotion: str | None = None
        self._vol: float = DEFAULT_VOLUME
        self._language_boost: str = DEFAULT_LANGUAGE_BOOST
        self._sample_rate: int = DEFAULT_SAMPLE_RATE
        self._bitrate: int = DEFAULT_BITRATE

        # Cache dir for served MP3s
        self._cache_dir = Path(hass.config.path("www")) / "minimax_tts"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Apply entry options as defaults
        if entry is not None:
            opts = entry.options
            self._voice_id = opts.get(CONF_VOICE_ID, DEFAULT_VOICE_ID)
            self._model = opts.get(CONF_MODEL, DEFAULT_MODEL)
            self._speed = opts.get(CONF_SPEED, DEFAULT_SPEED)
            self._pitch = opts.get(CONF_PITCH, DEFAULT_PITCH)
            self._emotion = opts.get(CONF_EMOTION) or None
            self._language_boost = opts.get(
                CONF_LANGUAGE_BOOST, DEFAULT_LANGUAGE_BOOST
            )
            self._sample_rate = opts.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE)
            self._bitrate = opts.get(CONF_BITRATE, DEFAULT_BITRATE)
            self._vol = opts.get(CONF_VOLUME, DEFAULT_VOLUME)

    @property
    def default_language(self) -> str:
        """Return the default language ISO code."""
        return "tr"

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return list(_LANG_MAP.keys())

    @property
    def supported_options(self) -> list[str]:
        """Return list of options that can be overridden per call."""
        return [
            CONF_VOICE_ID,
            CONF_MODEL,
            CONF_SPEED,
            CONF_PITCH,
            CONF_EMOTION,
            CONF_VOLUME,
            CONF_LANGUAGE_BOOST,
        ]

    @property
    def default_options(self) -> dict[str, Any]:
        """Return default options for the provider."""
        return {
            CONF_VOICE_ID: self._voice_id,
            CONF_MODEL: self._model,
            CONF_SPEED: self._speed,
            CONF_PITCH: self._pitch,
            CONF_EMOTION: self._emotion or "",
            CONF_VOLUME: self._vol,
            CONF_LANGUAGE_BOOST: self._language_boost,
        }

    @callback
    def async_get_supported_voices(self, language: str) -> list[Any] | None:
        """Return a list of supported voices for a language.

        Returning None means 'unspecified' (HA falls back to no-voice list).
        We return a curated subset to be useful in the UI without an extra call.
        """
        from homeassistant.components.tts import Voice

        voices = []
        if language.startswith("tr"):
            voices.extend(
                [
                    Voice("Turkish_Trustworthyman", "Turkish Trustworthy Man"),
                    Voice("Turkish_CalmWoman", "Turkish Calm Woman"),
                ]
            )
        elif language.startswith("en"):
            voices.extend(
                [
                    Voice("English_Graceful_Lady", "English Graceful Lady"),
                    Voice("English_Insightful_Speaker", "English Insightful Speaker"),
                    Voice("English_radiant_girl", "English Radiant Girl"),
                    Voice("English_Persuasive_Man", "English Persuasive Man"),
                    Voice("English_Aussie_Bloke", "English Aussie Bloke"),
                    Voice("English_Lucky_Robot", "English Lucky Robot"),
                ]
            )
        elif language.startswith("zh"):
            voices.extend(
                [
                    Voice(
                        "Chinese_(Mandarin)_Lyrical_Voice",
                        "Chinese (Mandarin) Lyrical Voice",
                    ),
                    Voice(
                        "Chinese_(Mandarin)_HK_Flight_Attendant",
                        "Chinese (Mandarin) HK Flight Attendant",
                    ),
                ]
            )
        elif language.startswith("ja"):
            voices.append(Voice("Japanese_Whisper_Belle", "Japanese Whisper Belle"))
        return voices or None

    def _resolve_options(self, options: dict[str, Any]) -> dict[str, Any]:
        """Merge defaults + entry options + call options (last wins)."""
        merged = self.default_options.copy()
        for key, val in (options or {}).items():
            if key in merged:
                merged[key] = val
        return merged

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Generate TTS audio and return (mime_type, url_or_bytes)."""
        if not message or not message.strip():
            return (None, None)

        # Truncate over-limit messages
        if len(message) > MAX_TEXT_LENGTH:
            _LOGGER.warning(
                "Mesaj %d karakter > %d, kesilecek",
                len(message),
                MAX_TEXT_LENGTH,
            )
            message = message[:MAX_TEXT_LENGTH]

        merged = self._resolve_options(options or {})

        # Resolve language_boost
        lb = merged.get(CONF_LANGUAGE_BOOST, DEFAULT_LANGUAGE_BOOST)
        if not lb or lb == "auto":
            if language and language in _LANG_MAP:
                lb = _LANG_MAP[language]
            else:
                lb = "auto"

        emotion = merged.get(CONF_EMOTION) or None
        if emotion == "":
            emotion = None

        req = TTSRequest(
            text=message,
            voice_id=merged[CONF_VOICE_ID],
            model=merged[CONF_MODEL],
            speed=float(merged[CONF_SPEED]),
            vol=float(merged.get(CONF_VOLUME, DEFAULT_VOLUME)),
            pitch=int(merged[CONF_PITCH]),
            emotion=emotion,
            sample_rate=self._sample_rate,
            bitrate=self._bitrate,
            language_boost=lb,
        )

        try:
            result = await self._client.synthesize(req)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("MiniMax TTS hatasi: %s", err)
            return (None, None)

        # Write to /config/www/minimax_tts/ for public serving
        filename = f"{secrets.token_hex(8)}.mp3"
        filepath = self._cache_dir / filename
        try:
            filepath.write_bytes(result.audio)
        except OSError as err:
            _LOGGER.error("Cache yazma hatasi: %s", err)
            return ("audio/mpeg", result.audio)

        try:
            base = get_url(self.hass, prefer_external=True)
            url = f"{base}/local/minimax_tts/{filename}"
        except Exception:  # noqa: BLE001
            url = f"/local/minimax_tts/{filename}"

        _LOGGER.debug(
            "MiniMax TTS: %s -> %s (%d bytes, %.2fs)",
            req.voice_id,
            url,
            result.audio_size,
            result.elapsed_seconds,
        )

        return ("audio/mpeg", url)
