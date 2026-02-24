"""The ClasseViva integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ClasseVivaAPI
from .const import DOMAIN, PLATFORMS, SERVICE_CLEANUP_DIDACTICS
from .coordinator import ClasseVivaCoordinator

_LOGGER = logging.getLogger(__name__)

# URL prefix under which the Lovelace card JavaScript is served
_CARD_URL_PATH = "/classeviva_card"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ClasseViva from a config entry."""
    session = async_get_clientsession(hass)
    api = ClasseVivaAPI(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session
    )
    await api.login()

    coordinator = ClasseVivaCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register the Lovelace card JavaScript as a static resource (once only)
    if not hass.data[DOMAIN].get("_card_registered"):
        www_dir = str(Path(__file__).parent / "www")
        hass.http.register_static_path(_CARD_URL_PATH, www_dir, cache_headers=False)
        hass.data[DOMAIN]["_card_registered"] = True
        _LOGGER.debug("Registered ClasseViva Lovelace card at %s", _CARD_URL_PATH)

    # Register the on-demand storage cleanup service
    async def _handle_cleanup(call: ServiceCall) -> None:  # noqa: ARG001
        removed = coordinator.cleanup_storage()
        _LOGGER.info(
            "classeviva.%s: removed %d stale didactic items",
            SERVICE_CLEANUP_DIDACTICS,
            removed,
        )

    hass.services.async_register(DOMAIN, SERVICE_CLEANUP_DIDACTICS, _handle_cleanup)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a ClasseViva config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
