"""Constants for the MiniMax TTS integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "minimax_tts"
MANUFACTURER: Final = "MiniMax"
DEFAULT_NAME: Final = "MiniMax TTS"

# API endpoints
CONF_BASE_URL: Final = "base_url"
DEFAULT_BASE_URL: Final = "https://api.minimax.io/v1/t2a_v2"
CN_BASE_URL: Final = "https://api.minimaxi.com/v1/t2a_v2"

# Config keys
CONF_API_KEY: Final = "api_key"
CONF_VOICE_ID: Final = "voice_id"
CONF_MODEL: Final = "model"
CONF_SPEED: Final = "speed"
CONF_VOLUME: Final = "vol"
CONF_PITCH: Final = "pitch"
CONF_EMOTION: Final = "emotion"
CONF_SAMPLE_RATE: Final = "sample_rate"
CONF_BITRATE: Final = "bitrate"
CONF_LANGUAGE_BOOST: Final = "language_boost"

# Defaults
DEFAULT_MODEL: Final = "speech-2.8-hd"
DEFAULT_VOICE_ID: Final = "English_Graceful_Lady"
DEFAULT_SPEED: Final = 1.0
DEFAULT_VOLUME: Final = 1.0
DEFAULT_PITCH: Final = 0
DEFAULT_SAMPLE_RATE: Final = 32000
DEFAULT_BITRATE: Final = 128000
DEFAULT_LANGUAGE_BOOST: Final = "auto"

AVAILABLE_MODELS: Final = (
    "speech-2.8-hd",
    "speech-2.8-turbo",
    "speech-2.6-hd",
    "speech-2.6-turbo",
    "speech-02-hd",
    "speech-02-turbo",
    "speech-01-hd",
    "speech-01-turbo",
)

AVAILABLE_EMOTIONS: Final = (
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgusted",
    "surprised",
    "calm",
    "fluent",
    "whisper",
)

AVAILABLE_LANGUAGE_BOOSTS: Final = (
    "auto",
    "Chinese",
    "Chinese,Yue",
    "English",
    "Arabic",
    "Russian",
    "Spanish",
    "French",
    "Portuguese",
    "German",
    "Italian",
    "Japanese",
    "Korean",
    "Indonesian",
    "Vietnamese",
    "Turkish",
    "Dutch",
    "Ukrainian",
    "Thai",
    "Polish",
    "Romanian",
    "Greek",
    "Czech",
    "Finnish",
    "Hindi",
)

CACHE_DIR: Final = "minimax_tts"
MAX_TEXT_LENGTH: Final = 10000
REQUEST_TIMEOUT: Final = 60

STATUS_SUCCESS: Final = 0
STATUS_QUOTA_EXCEEDED: Final = 1002
STATUS_AUTH_FAILED: Final = 1004
STATUS_INVALID_CHARS: Final = 1042
