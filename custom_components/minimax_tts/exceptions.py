"""Custom exceptions for the MiniMax TTS integration."""
from __future__ import annotations


class MiniMaxTTSError(Exception):
    """Base exception for MiniMax TTS integration."""


class MiniMaxAuthError(MiniMaxTTSError):
    """Raised when API key authentication fails (status 1004)."""


class MiniMaxQuotaExceededError(MiniMaxTTSError):
    """Raised when rate limit or quota is exceeded (status 1002)."""


class MiniMaxInvalidCharactersError(MiniMaxTTSError):
    """Raised when invalid characters exceed 10% (status 1042)."""


class MiniMaxAPIError(MiniMaxTTSError):
    """Raised for any other MiniMax API error."""

    def __init__(self, status_code: int, status_msg: str) -> None:
        super().__init__(f"MiniMax API error {status_code}: {status_msg}")
        self.status_code = status_code
        self.status_msg = status_msg


class MiniMaxConnectionError(MiniMaxTTSError):
    """Raised when connection to MiniMax API fails."""


class MiniMaxConfigError(MiniMaxTTSError):
    """Raised when configuration is invalid."""
