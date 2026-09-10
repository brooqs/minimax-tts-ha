"""MiniMax TTS integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN
from .coordinator import MiniMaxTTSClient, TTSRequest

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config entry'yi kur."""
    api_key = entry.data.get(CONF_API_KEY)
    base_url = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)

    if not api_key:
        _LOGGER.error("API key eksik: %s", entry.entry_id)
        return False

    client = MiniMaxTTSClient(api_key=api_key, base_url=base_url)

    try:
        await client.__aenter__()
        # Hızlı doğrulama: küçük bir ses üretmeyi dene
        await client.synthesize(
            TTSRequest(text="test", voice_id="English_Graceful_Lady")
        )
    except Exception as err:
        _LOGGER.warning("MiniMax API doğrulama hatası: %s", err)
        if "auth" in str(err).lower() or "1004" in str(err):
            await client.__aexit__(None, None, None)
            raise ConfigEntryNotReady(f"API auth hatası: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "entry": entry,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config entry'yi kaldır."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data and "client" in data:
            try:
                await data["client"].__aexit__(None, None, None)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Client kapatma hatası: %s", err)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Options değiştiğinde entry'yi yeniden yükle."""
    await hass.config_entries.async_reload(entry.entry_id)
