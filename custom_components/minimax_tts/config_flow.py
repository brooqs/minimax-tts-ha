"""Config flow for MiniMax TTS integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

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
    CN_BASE_URL,
    DEFAULT_BASE_URL,
    DEFAULT_BITRATE,
    DEFAULT_LANGUAGE_BOOST,
    DEFAULT_MODEL,
    DEFAULT_PITCH,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SPEED,
    DEFAULT_VOICE_ID,
    DOMAIN,
)
from .coordinator import MiniMaxTTSClient, TTSRequest
from .exceptions import MiniMaxAuthError, MiniMaxConnectionError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): vol.In(
            [DEFAULT_BASE_URL, CN_BASE_URL]
        ),
    }
)


class MiniMaxTTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MiniMax TTS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            base_url = user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL)

            unique_id = f"minimax_{hash(api_key) & 0xffffffff:08x}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            client = MiniMaxTTSClient(api_key=api_key, base_url=base_url)
            try:
                async with client:
                    await client.synthesize(
                        TTSRequest(text="test", voice_id=DEFAULT_VOICE_ID)
                    )
            except MiniMaxAuthError:
                errors["base"] = "invalid_auth"
            except MiniMaxConnectionError as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("MiniMax bağlantı hatası: %s", err)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Beklenmeyen hata: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="MiniMax TTS",
                    data={
                        CONF_API_KEY: api_key,
                        CONF_BASE_URL: base_url,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://platform.minimax.io/user-center/basic-information/interface-key",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "MiniMaxTTSOptionsFlow":
        return MiniMaxTTSOptionsFlow()


class MiniMaxTTSOptionsFlow(OptionsFlow):
    """MiniMax TTS options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MODEL,
                    default=opts.get(CONF_MODEL, DEFAULT_MODEL),
                ): vol.In(AVAILABLE_MODELS),
                vol.Optional(
                    CONF_VOICE_ID,
                    default=opts.get(CONF_VOICE_ID, DEFAULT_VOICE_ID),
                ): cv.string,
                vol.Optional(
                    CONF_SPEED,
                    default=opts.get(CONF_SPEED, DEFAULT_SPEED),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=2.0)),
                vol.Optional(
                    CONF_PITCH,
                    default=opts.get(CONF_PITCH, DEFAULT_PITCH),
                ): vol.All(int, vol.Range(min=-12, max=12)),
                vol.Optional(
                    CONF_EMOTION,
                    default=opts.get(CONF_EMOTION, ""),
                ): vol.In([""] + list(AVAILABLE_EMOTIONS)),
                vol.Optional(
                    CONF_LANGUAGE_BOOST,
                    default=opts.get(CONF_LANGUAGE_BOOST, DEFAULT_LANGUAGE_BOOST),
                ): vol.In(list(AVAILABLE_LANGUAGE_BOOSTS)),
                vol.Optional(
                    CONF_SAMPLE_RATE,
                    default=opts.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE),
                ): vol.In([8000, 16000, 22050, 24000, 32000, 44100]),
                vol.Optional(
                    CONF_BITRATE,
                    default=opts.get(CONF_BITRATE, DEFAULT_BITRATE),
                ): vol.In([32000, 64000, 128000, 256000]),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
