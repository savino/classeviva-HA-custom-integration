"""DataUpdateCoordinator for ClasseViva.

Fetches all student data from the Spaggiari API on a regular schedule and
fires Home Assistant events whenever new content is detected in:
  - Area didattica  (classeviva_new_didactics)
  - Bacheca         (classeviva_new_noticeboard)
  - Agenda          (classeviva_new_agenda)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ClasseVivaAPI
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_AGENDA,
    EVENT_NEW_DIDACTICS,
    EVENT_NEW_NOTICEBOARD,
)

_LOGGER = logging.getLogger(__name__)

# How far into the future to query agenda events
_AGENDA_LOOKAHEAD_DAYS = 30


class ClasseVivaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls all ClasseViva endpoints."""

    def __init__(self, hass: HomeAssistant, api: ClasseVivaAPI) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        # Sets of IDs already seen – used to detect new content
        self._seen_didactics: set[int] = set()
        self._seen_noticeboard: set[int] = set()
        self._seen_agenda: set[int] = set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_didactics_ids(self, teachers: list[dict]) -> set[int]:
        ids: set[int] = set()
        for teacher in teachers:
            for folder in teacher.get("folders", []):
                for item in folder.get("agendaItems", []):
                    ids.add(item.get("itemId") or item.get("contentId"))
        return ids

    def _fire_new_didactics(self, teachers: list[dict]) -> None:
        """Fire an event for every new didactics item."""
        for teacher in teachers:
            for folder in teacher.get("folders", []):
                for item in folder.get("agendaItems", []):
                    item_id = item.get("itemId") or item.get("contentId")
                    if item_id not in self._seen_didactics:
                        self.hass.bus.async_fire(
                            EVENT_NEW_DIDACTICS,
                            {
                                "teacher": teacher.get("teacherName"),
                                "folder": folder.get("folderName"),
                                "item_name": item.get("displayName") or item.get("itemName"),
                                "share_date": item.get("shareDt"),
                            },
                        )

    def _fire_new_noticeboard(self, items: list[dict]) -> None:
        """Fire an event for every new noticeboard notice."""
        for item in items:
            pub_id = item.get("pubId")
            if pub_id not in self._seen_noticeboard:
                self.hass.bus.async_fire(
                    EVENT_NEW_NOTICEBOARD,
                    {
                        "title": item.get("cntTitle"),
                        "author": item.get("cntAuthor"),
                        "category": item.get("cntCategory"),
                        "begin": item.get("evtBegin"),
                    },
                )

    def _fire_new_agenda(self, events: list[dict]) -> None:
        """Fire an event for every new agenda entry."""
        for event in events:
            evt_id = event.get("evtId")
            if evt_id not in self._seen_agenda:
                self.hass.bus.async_fire(
                    EVENT_NEW_AGENDA,
                    {
                        "notes": event.get("notes"),
                        "author": event.get("authorName"),
                        "subject": event.get("subjectDesc"),
                        "begin": event.get("evtDatetimeBegin"),
                        "end": event.get("evtDatetimeEnd"),
                    },
                )

    # ------------------------------------------------------------------
    # Coordinator update
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data from the API."""
        try:
            grades = await self.api.grades()
            absences = await self.api.absences()
            now = datetime.now()
            agenda = await self.api.agenda(now, now + timedelta(days=_AGENDA_LOOKAHEAD_DAYS))
            didactics = await self.api.didactics()
            noticeboard = await self.api.noticeboard()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error communicating with ClasseViva API: {err}") from err

        # Fire events for newly detected content (skip the very first fetch to
        # avoid flooding the bus after a restart)
        if self._seen_didactics or self._seen_noticeboard or self._seen_agenda:
            self._fire_new_didactics(didactics)
            self._fire_new_noticeboard(noticeboard)
            self._fire_new_agenda(agenda)

        # Update seen-ID sets
        self._seen_didactics = self._collect_didactics_ids(didactics)
        self._seen_noticeboard = {item.get("pubId") for item in noticeboard}
        self._seen_agenda = {event.get("evtId") for event in agenda}

        return {
            "grades": grades,
            "absences": absences,
            "agenda": agenda,
            "didactics": didactics,
            "noticeboard": noticeboard,
        }
