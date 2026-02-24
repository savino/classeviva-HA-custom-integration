"""Shared test fixtures and HA module stubs."""
from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub all Home Assistant packages before anything else is imported.
# This allows our integration modules to be imported without a real HA install.
# ---------------------------------------------------------------------------

_HA_STUBS = [
    "homeassistant",
    "homeassistant.core",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.entity_platform",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.components.calendar",
    "homeassistant.util",
    "homeassistant.util.dt",
]
for _mod in _HA_STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_upd = sys.modules["homeassistant.helpers.update_coordinator"]


class _GenericCoordinator:
    """Subscriptable stub for DataUpdateCoordinator."""

    def __class_getitem__(cls, item):
        return cls


_upd.DataUpdateCoordinator = _GenericCoordinator  # type: ignore[attr-defined]
_upd.UpdateFailed = Exception  # type: ignore[attr-defined]
_upd.CoordinatorEntity = object  # type: ignore[attr-defined]

_sens = sys.modules["homeassistant.components.sensor"]
_sens.SensorEntity = object  # type: ignore[attr-defined]
_sens.SensorStateClass = MagicMock()  # type: ignore[attr-defined]

_cal = sys.modules["homeassistant.components.calendar"]
_cal.CalendarEntity = object  # type: ignore[attr-defined]
_cal.CalendarEvent = MagicMock()  # type: ignore[attr-defined]

_dt = sys.modules["homeassistant.util.dt"]
_dt.parse_datetime = MagicMock(return_value=None)  # type: ignore[attr-defined]

_ce = sys.modules["homeassistant.config_entries"]
_ce.ConfigEntry = object  # type: ignore[attr-defined]
_ce.ConfigFlow = object  # type: ignore[attr-defined]
_ce.ConfigFlowResult = object  # type: ignore[attr-defined]

_const = sys.modules["homeassistant.const"]
_const.CONF_USERNAME = "username"  # type: ignore[attr-defined]
_const.CONF_PASSWORD = "password"  # type: ignore[attr-defined]

_core = sys.modules["homeassistant.core"]
_core.HomeAssistant = object  # type: ignore[attr-defined]
_core.ServiceCall = object  # type: ignore[attr-defined]

_aio = sys.modules["homeassistant.helpers.aiohttp_client"]
_aio.async_get_clientsession = MagicMock()  # type: ignore[attr-defined]

_ent = sys.modules["homeassistant.helpers.entity_platform"]
_ent.AddEntitiesCallback = object  # type: ignore[attr-defined]

# Make the repo root available and register the custom_components package
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Pre-register the package so relative imports inside our modules work
import custom_components.classeviva  # noqa: E402  – triggers __init__ early
