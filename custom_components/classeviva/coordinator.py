"""DataUpdateCoordinator for ClasseViva.

Fetches all student data from the Spaggiari API on a regular schedule and
fires Home Assistant events whenever new content is detected in:
  - Area didattica  (classeviva_new_didactics)
  - Bacheca         (classeviva_new_noticeboard)
  - Agenda          (classeviva_new_agenda)
  - Agenda event personally concerning the student
                    (classeviva_student_agenda_event)

New didactic attachments are automatically downloaded to
``<config>/www/classeviva_didactics/`` (served at ``/local/classeviva_didactics/``)
and older cached files are purged after 60 days.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ClasseVivaAPI
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DIDACTICS_MAX_AGE_DAYS,
    DOMAIN,
    EVENT_NEW_AGENDA,
    EVENT_NEW_DIDACTICS,
    EVENT_NEW_NOTICEBOARD,
    EVENT_STUDENT_AGENDA,
)
from .storage import DidacticsStorage

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
        # Local storage for didactic attachments
        self._storage = DidacticsStorage(Path(hass.config.path("www")))

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def cleanup_storage(self, max_age_days: int = DIDACTICS_MAX_AGE_DAYS) -> int:
        """Remove cached didactic files older than *max_age_days* days.

        Returns the number of items removed.  Delegates to the underlying
        :class:`~.storage.DidacticsStorage` instance.
        """
        removed = self._storage.cleanup_old_content(max_age_days)
        if removed:
            _LOGGER.debug("Cleaned up %d stale didactic items from local storage", removed)
        return removed

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

    def _fire_student_agenda_events(self, events: list[dict]) -> None:
        """Fire ``EVENT_STUDENT_AGENDA`` for new events that concern the student."""
        for event in events:
            evt_id = event.get("evtId")
            if evt_id not in self._seen_agenda and event.get("student_relevant"):
                self.hass.bus.async_fire(
                    EVENT_STUDENT_AGENDA,
                    {
                        "notes": event.get("notes"),
                        "author": event.get("authorName"),
                        "subject": event.get("subjectDesc"),
                        "begin": event.get("evtDatetimeBegin"),
                        "end": event.get("evtDatetimeEnd"),
                    },
                )

    @staticmethod
    def _is_student_relevant(event: dict, student_last_name: str) -> bool:
        """Return True when *event* seems to directly concern the student.

        An event is considered personally relevant when the student's last name
        appears in the event notes (e.g. "Rossi – interrogazione orale").
        """
        if not student_last_name:
            return False
        notes = (event.get("notes") or "").lower()
        return student_last_name.lower() in notes

    async def _download_new_didactics(self, teachers: list[dict]) -> None:
        """Download and cache any didactic item not yet stored locally."""
        for teacher in teachers:
            for folder in teacher.get("folders", []):
                for item in folder.get("agendaItems", []):
                    item_id = item.get("itemId") or item.get("contentId")
                    if item_id is None or self._storage.has_content(item_id):
                        continue
                    content_id = item.get("contentId") or item.get("itemId")
                    try:
                        data = await self.api.download_didactic_content(content_id)
                        if data:
                            filename = (
                                item.get("displayName")
                                or item.get("itemName")
                                or f"item_{item_id}"
                            )
                            self._storage.save_content(item_id, filename, data)
                    except Exception:  # noqa: BLE001
                        _LOGGER.warning(
                            "Failed to download didactic item %s", item_id
                        )

    def _attach_local_urls(self, teachers: list[dict]) -> None:
        """Add ``local_url`` key to each didactic item dict (in-place)."""
        for teacher in teachers:
            for folder in teacher.get("folders", []):
                for item in folder.get("agendaItems", []):
                    item_id = item.get("itemId") or item.get("contentId")
                    if item_id is not None:
                        item["local_url"] = self._storage.local_url(item_id)

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

        # Annotate each agenda event with a student-relevance flag
        student_last_name = self.api.last_name or ""
        for event in agenda:
            event["student_relevant"] = self._is_student_relevant(
                event, student_last_name
            )

        # Fire events for newly detected content (skip the very first fetch to
        # avoid flooding the bus after a restart)
        if self._seen_didactics or self._seen_noticeboard or self._seen_agenda:
            self._fire_new_didactics(didactics)
            self._fire_new_noticeboard(noticeboard)
            self._fire_new_agenda(agenda)
            self._fire_student_agenda_events(agenda)

        # Update seen-ID sets
        self._seen_didactics = self._collect_didactics_ids(didactics)
        self._seen_noticeboard = {item.get("pubId") for item in noticeboard}
        self._seen_agenda = {event.get("evtId") for event in agenda}

        # Download any new didactic attachments (best-effort, non-blocking on error)
        await self._download_new_didactics(didactics)

        # Remove cached files older than 60 days
        self.cleanup_storage()

        # Annotate didactic items with their local download URLs
        self._attach_local_urls(didactics)

        return {
            "grades": grades,
            "absences": absences,
            "agenda": agenda,
            "didactics": didactics,
            "noticeboard": noticeboard,
        }

