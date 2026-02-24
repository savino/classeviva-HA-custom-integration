"""Config flow for the ClasseViva integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthenticationError, ClasseVivaAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ClasseVivaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ClasseViva."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = ClasseVivaAPI(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session
            )
            try:
                info = await api.login()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during ClasseViva login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{info['first_name']} {info['last_name']}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
