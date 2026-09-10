"""TTS platform for MiniMax TTS integration.

Modern pattern using TextToSpeechEntity (HA 2024.4+).
See homeassistant/components/tts/entity.py for the base class.

Custom components expose TTS engines as entities — not providers.
Engine id is derived from the entity_id (tts.<slug>).
"""
from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any

from homeassistant.components.tts import (
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTRIBUTION,
    ATTRIBUTION_URL,
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

# Per-language defaults - MiniMax can detect language, but we forward
# an explicit language_boost when caller provides an ISO code.
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


# Curated voice list per language - returned by async_get_supported_voices
# so the HA UI shows them in the voice picker.
_VOICES_BY_LANG: dict[str, list[tuple[str, str]]] = {
    "tr": [
        ("Turkish_Trustworthyman", "Turkish Trustworthy Man"),
        ("Turkish_CalmWoman", "Turkish Calm Woman"),
    ],
    "en": [
        ("English_Graceful_Lady", "English Graceful Lady"),
        ("English_Insightful_Speaker", "English Insightful Speaker"),
        ("English_radiant_girl", "English Radiant Girl"),
        ("English_Persuasive_Man", "English Persuasive Man"),
        ("English_Aussie_Bloke", "English Aussie Bloke"),
        ("English_Lucky_Robot", "English Lucky Robot"),
    ],
    "zh": [
        ("Chinese_(Mandarin)_Lyrical_Voice", "Chinese (Mandarin) Lyrical Voice"),
        (
            "Chinese_(Mandarin)_HK_Flight_Attendant",
            "Chinese (Mandarin) HK Flight Attendant",
        ),
    ],
    "ja": [
        ("Japanese_Whisper_Belle", "Japanese Whisper Belle"),
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MiniMax TTS entity from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: MiniMaxTTSClient = data["client"]

    async_add_entities(
        [MiniMaxTTSEntity(hass, config_entry, client)], update_before_add=True
    )


class MiniMaxTTSEntity(TextToSpeechEntity):
    """MiniMax TTS engine entity.

    Inherits from TextToSpeechEntity (HA 2024.4+) which is a proper HA entity.
    Appears in the entity registry as `tts.minimax_tts`.
    """

    # Required attributes
    _attr_default_language: str = "tr"
    _attr_supported_languages: list[str] = list(_LANG_MAP.keys())
    _attr_supported_options: list[str] = [
        CONF_VOICE_ID,
        "voice",  # HA's standard voice option (maps to voice_id)
        CONF_MODEL,
        CONF_SPEED,
        CONF_PITCH,
        CONF_EMOTION,
        CONF_VOLUME,
        CONF_LANGUAGE_BOOST,
    ]

    # Branding — shown in HA device registry and diagnostics
    _attr_attribution: str | None = f"{ATTRIBUTION} - {ATTRIBUTION_URL}"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MiniMaxTTSClient,
    ) -> None:
        """Initialize the entity."""
        self.hass = hass
        self._entry = entry
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_tts"
        self._attr_name = "MiniMax TTS"

        # Defaults applied via entry.options, fall back to module defaults
        opts = entry.options
        self._voice_id: str = opts.get(CONF_VOICE_ID, DEFAULT_VOICE_ID)
        self._model: str = opts.get(CONF_MODEL, DEFAULT_MODEL)
        self._speed: float = opts.get(CONF_SPEED, DEFAULT_SPEED)
        self._pitch: int = opts.get(CONF_PITCH, DEFAULT_PITCH)
        self._emotion: str | None = opts.get(CONF_EMOTION) or None
        self._vol: float = opts.get(CONF_VOLUME, DEFAULT_VOLUME)
        self._language_boost: str = opts.get(
            CONF_LANGUAGE_BOOST, DEFAULT_LANGUAGE_BOOST
        )
        self._sample_rate: int = opts.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE)
        self._bitrate: int = opts.get(CONF_BITRATE, DEFAULT_BITRATE)

        # Cache dir for served MP3s
        self._cache_dir = Path(hass.config.path("www")) / "minimax_tts"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def default_options(self) -> dict[str, Any]:
        """Return default options (overrides per-call defaults)."""
        return {
            CONF_VOICE_ID: self._voice_id,
            "voice": self._voice_id,  # alias for HA's standard voice option
            CONF_MODEL: self._model,
            CONF_SPEED: self._speed,
            CONF_PITCH: self._pitch,
            CONF_EMOTION: self._emotion or "",
            CONF_VOLUME: self._vol,
            CONF_LANGUAGE_BOOST: self._language_boost,
        }

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return supported voices for the requested language code."""
        lang_key = language.split("-")[0] if language else ""
        voices = _VOICES_BY_LANG.get(lang_key, [])
        return [Voice(vid, name) for vid, name in voices] or None

    def _resolve_options(self, options: dict[str, Any] | None) -> dict[str, Any]:
        """Merge: defaults < per-call options (per-call wins).

        Maps HA's standard 'voice' key onto our CONF_VOICE_ID.
        """
        merged = self.default_options.copy()
        for key, val in (options or {}).items():
            if key in merged:
                merged[key] = val
            elif key == "voice":
                # HA standard 'voice' alias -> our voice_id
                merged[CONF_VOICE_ID] = val
                merged["voice"] = val
        return merged

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Generate TTS audio.

        Args:
            message: The text to speak.
            language: ISO language code (e.g. 'tr', 'en').
            options: Per-call overrides for voice_id, speed, etc.

        Returns:
            (mime_type, url_or_bytes) tuple.
        """
        if not message or not message.strip():
            return (None, None)

        if len(message) > MAX_TEXT_LENGTH:
            _LOGGER.warning(
                "Message %d chars > %d, truncating",
                len(message),
                MAX_TEXT_LENGTH,
            )
            message = message[:MAX_TEXT_LENGTH]

        merged = self._resolve_options(options)

        # Resolve language_boost from ISO code when caller used auto
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
            _LOGGER.error("MiniMax TTS error: %s", err)
            return (None, None)

        # Cache the MP3 and serve via /config/www/minimax_tts/
        filename = f"{secrets.token_hex(8)}.mp3"
        filepath = self._cache_dir / filename
        try:
            filepath.write_bytes(result.audio)
        except OSError as err:
            _LOGGER.error("Cache write error: %s", err)
            return ("audio/mpeg", result.audio)

        # Always return a RELATIVE URL — HA will resolve it against its own
        # base_url (internal_url if configured, otherwise external). This
        # avoids reachability issues when external_url (home.dhy.tr) is not
        # accessible from the media player (LAN/mesh only).
        url = f"/local/minimax_tts/{filename}"

        _LOGGER.debug(
            "MiniMax TTS: %s -> %s (%d bytes, %.2fs)",
            req.voice_id,
            url,
            result.audio_size,
            result.elapsed_seconds,
        )

        return ("audio/mpeg", url)
