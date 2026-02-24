"""Calendar platform for ClasseViva.

Exposes the student's agenda as a Home Assistant calendar entity so that
events can be viewed in the HA Calendar dashboard and exported as iCal.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import parse_datetime

from .const import DOMAIN
from .coordinator import ClasseVivaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ClasseViva calendar entity."""
    coordinator: ClasseVivaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ClasseVivaCalendar(coordinator, entry)])


class ClasseVivaCalendar(CoordinatorEntity[ClasseVivaCoordinator], CalendarEntity):
    """Calendar entity representing the student's agenda."""

    _attr_has_entity_name = True
    _attr_name = "Agenda"
    _attr_icon = "mdi:calendar"

    def __init__(
        self, coordinator: ClasseVivaCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": self.coordinator.config_entry.title,
            "manufacturer": "Spaggiari",
            "model": "ClasseViva",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _raw_to_event(self, raw: dict) -> CalendarEvent | None:
        """Convert a raw API agenda dict to a :class:`CalendarEvent`."""
        begin_str = raw.get("evtDatetimeBegin")
        end_str = raw.get("evtDatetimeEnd")

        if not begin_str or not end_str:
            return None

        start = parse_datetime(begin_str)
        end = parse_datetime(end_str)

        if start is None or end is None:
            return None

        # Ensure end > start to satisfy HA validation
        if end <= start:
            end = start + timedelta(hours=1)

        summary = (
            raw.get("notes")
            or raw.get("subjectDesc")
            or raw.get("evtCode")
            or "Event"
        )

        return CalendarEvent(
            start=start,
            end=end,
            summary=summary,
            description=(
                f"Teacher: {raw.get('authorName', '')}\n"
                f"Subject: {raw.get('subjectDesc', '')}\n"
                f"Notes: {raw.get('notes', '')}"
            ),
        )

    # ------------------------------------------------------------------
    # CalendarEntity interface
    # ------------------------------------------------------------------

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming calendar event."""
        now = datetime.utcnow()
        upcoming = []
        for raw in self.coordinator.data.get("agenda", []):
            begin_str = raw.get("evtDatetimeBegin", "")
            begin = parse_datetime(begin_str)
            if begin and begin.replace(tzinfo=None) >= now:
                upcoming.append((begin, raw))

        if not upcoming:
            return None

        upcoming.sort(key=lambda t: t[0])
        return self._raw_to_event(upcoming[0][1])

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events in the given date range."""
        events: list[CalendarEvent] = []
        for raw in self.coordinator.data.get("agenda", []):
            begin_str = raw.get("evtDatetimeBegin", "")
            begin = parse_datetime(begin_str)
            if begin is None:
                continue
            # Compare timezone-aware datetimes correctly
            begin_naive = begin.replace(tzinfo=None)
            start_naive = start_date.replace(tzinfo=None)
            end_naive = end_date.replace(tzinfo=None)
            if start_naive <= begin_naive <= end_naive:
                event = self._raw_to_event(raw)
                if event is not None:
                    events.append(event)
        return events
