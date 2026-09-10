"""Tests for MiniMax TTS coordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.minimax_tts.coordinator import (
    MiniMaxTTSClient,
    TTSRequest,
)
from custom_components.minimax_tts.exceptions import (
    MiniMaxAuthError,
    MiniMaxConnectionError,
    MiniMaxInvalidCharactersError,
    MiniMaxQuotaExceededError,
)


@pytest.fixture
def api_key() -> str:
    return "test_api_key_12345"


@pytest.fixture
def mock_hex_audio() -> str:
    return "49443304000000000800000000"


@pytest.mark.asyncio
async def test_client_init_validates_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        MiniMaxTTSClient(api_key="")


@pytest.mark.asyncio
async def test_synthesize_success(api_key: str, mock_hex_audio: str) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "data": {"audio": mock_hex_audio, "status": 2},
            "extra_info": {
                "audio_size": len(mock_hex_audio) // 2,
                "audio_length": 2000,
                "audio_sample_rate": 32000,
                "bitrate": 128000,
                "word_count": 5,
                "usage_characters": 30,
            },
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }
    )
    mock_response.read = AsyncMock(return_value=b"")

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

        async with MiniMaxTTSClient(api_key=api_key) as client:
            req = TTSRequest(text="Merhaba dunya", voice_id="Turkish_Trustworthyman")
            result = await client.synthesize(req)

        assert result.audio == bytes.fromhex(mock_hex_audio)
        assert result.usage_characters == 30
        assert result.word_count == 5


@pytest.mark.asyncio
async def test_synthesize_auth_failed(api_key: str) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "data": {"audio": "", "status": 1},
            "extra_info": {},
            "base_resp": {"status_code": 1004, "status_msg": "invalid api key"},
        }
    )
    mock_response.read = AsyncMock(return_value=b"")

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

        async with MiniMaxTTSClient(api_key=api_key) as client:
            req = TTSRequest(text="test", voice_id="English_Graceful_Lady")
            with pytest.raises(MiniMaxAuthError):
                await client.synthesize(req)


@pytest.mark.asyncio
async def test_synthesize_quota_exceeded(api_key: str) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "data": {"audio": "", "status": 1},
            "extra_info": {},
            "base_resp": {"status_code": 1002, "status_msg": "rate limit"},
        }
    )
    mock_response.read = AsyncMock(return_value=b"")

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

        async with MiniMaxTTSClient(api_key=api_key) as client:
            req = TTSRequest(text="test", voice_id="English_Graceful_Lady")
            with pytest.raises(MiniMaxQuotaExceededError):
                await client.synthesize(req)


@pytest.mark.asyncio
async def test_synthesize_invalid_chars(api_key: str) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "data": {"audio": "", "status": 1},
            "extra_info": {},
            "base_resp": {"status_code": 1042, "status_msg": "too many invalid chars"},
        }
    )
    mock_response.read = AsyncMock(return_value=b"")

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

        async with MiniMaxTTSClient(api_key=api_key) as client:
            req = TTSRequest(text="test", voice_id="English_Graceful_Lady")
            with pytest.raises(MiniMaxInvalidCharactersError):
                await client.synthesize(req)


@pytest.mark.asyncio
async def test_synthesize_connection_error(api_key: str) -> None:
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.read = AsyncMock(return_value=b"Internal Server Error")

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

        async with MiniMaxTTSClient(api_key=api_key) as client:
            req = TTSRequest(text="test", voice_id="English_Graceful_Lady")
            with pytest.raises(MiniMaxConnectionError):
                await client.synthesize(req)


@pytest.mark.asyncio
async def test_synthesize_empty_text(api_key: str) -> None:
    async with MiniMaxTTSClient(api_key=api_key) as client:
        with pytest.raises(ValueError, match="bos"):
            await client.synthesize(TTSRequest(text="", voice_id="English_Graceful_Lady"))
        with pytest.raises(ValueError, match="bos"):
            await client.synthesize(TTSRequest(text="   ", voice_id="English_Graceful_Lady"))


@pytest.mark.asyncio
async def test_synthesize_text_too_long(api_key: str) -> None:
    long_text = "a" * 10001
    async with MiniMaxTTSClient(api_key=api_key) as client:
        with pytest.raises(ValueError, match="10000"):
            await client.synthesize(TTSRequest(text=long_text, voice_id="English_Graceful_Lady"))


@pytest.mark.asyncio
async def test_payload_includes_all_options(api_key: str) -> None:
    client = MiniMaxTTSClient(api_key=api_key)
    req = TTSRequest(
        text="test",
        voice_id="Turkish_CalmWoman",
        model="speech-2.8-turbo",
        speed=1.2,
        vol=0.8,
        pitch=3,
        emotion="calm",
        sample_rate=24000,
        bitrate=64000,
        language_boost="Turkish",
    )
    payload = client._build_payload(req)

    assert payload["model"] == "speech-2.8-turbo"
    assert payload["voice_setting"]["voice_id"] == "Turkish_CalmWoman"
    assert payload["voice_setting"]["speed"] == 1.2
    assert payload["voice_setting"]["vol"] == 0.8
    assert payload["voice_setting"]["pitch"] == 3
    assert payload["voice_setting"]["emotion"] == "calm"
    assert payload["audio_setting"]["sample_rate"] == 24000
    assert payload["audio_setting"]["bitrate"] == 64000
    assert payload["audio_setting"]["format"] == "mp3"
    assert payload["language_boost"] == "Turkish"
    assert payload["stream"] is False
    assert payload["output_format"] == "hex"


@pytest.mark.asyncio
async def test_payload_omits_emotion_when_none(api_key: str) -> None:
    client = MiniMaxTTSClient(api_key=api_key)
    req = TTSRequest(text="test", voice_id="English_Graceful_Lady", emotion=None)
    payload = client._build_payload(req)
    assert "emotion" not in payload["voice_setting"]
