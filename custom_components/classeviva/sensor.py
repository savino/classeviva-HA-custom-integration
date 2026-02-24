"""Sensor platform for ClasseViva.

Provides the following sensors per student account:
  - Average grade (state = numeric average across all grades)
  - Unjustified absences (state = count)
  - Noticeboard notices (state = total count, unread highlighted in attributes)
  - Didactics items (state = total count across all folders)
  - Next agenda event (state = event description / notes)
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ClasseVivaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ClasseViva sensor entities."""
    coordinator: ClasseVivaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ClasseVivaGradesSensor(coordinator, entry),
            ClasseVivaAbsencesSensor(coordinator, entry),
            ClasseVivaNoticeboardSensor(coordinator, entry),
            ClasseVivaDidacticsSensor(coordinator, entry),
            ClasseVivaNextAgendaSensor(coordinator, entry),
        ]
    )


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class ClasseVivaBaseSensor(CoordinatorEntity[ClasseVivaCoordinator], SensorEntity):
    """Base sensor for ClasseViva entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ClasseVivaCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info so all sensors are grouped together."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": self.coordinator.config_entry.title,
            "manufacturer": "Spaggiari",
            "model": "ClasseViva",
        }


# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------


class ClasseVivaGradesSensor(ClasseVivaBaseSensor):
    """Average grade sensor."""

    _attr_name = "Average Grade"
    _attr_icon = "mdi:school"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator: ClasseVivaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "grades")

    @property
    def native_value(self) -> float | None:
        """Return the mean of all non-zero decimal grades."""
        grades = self.coordinator.data.get("grades", [])
        values = [
            g["decimalValue"]
            for g in grades
            if g.get("decimalValue") and g["decimalValue"] > 0
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the most recent 10 grades as attributes."""
        grades = self.coordinator.data.get("grades", [])
        recent = sorted(grades, key=lambda g: g.get("evtDate", ""), reverse=True)[:10]
        return {
            "recent_grades": [
                {
                    "date": g.get("evtDate"),
                    "subject": g.get("subjectDesc"),
                    "value": g.get("displayValue"),
                    "notes": g.get("notesForFamily"),
                }
                for g in recent
            ]
        }


# ---------------------------------------------------------------------------
# Absences
# ---------------------------------------------------------------------------


class ClasseVivaAbsencesSensor(ClasseVivaBaseSensor):
    """Unjustified absence counter sensor."""

    _attr_name = "Unjustified Absences"
    _attr_icon = "mdi:account-off"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "absences"

    def __init__(self, coordinator: ClasseVivaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "absences")

    @property
    def native_value(self) -> int:
        """Return the count of unjustified absences."""
        absences = self.coordinator.data.get("absences", [])
        return sum(1 for a in absences if not a.get("isJustified", True))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        absences = self.coordinator.data.get("absences", [])
        return {
            "absences": [
                {
                    "date": a.get("evtDate"),
                    "type": a.get("evtCode"),
                    "justified": a.get("isJustified"),
                    "reason": a.get("justifReasonDesc"),
                }
                for a in absences
            ],
            "total_absences": len(absences),
        }


# ---------------------------------------------------------------------------
# Noticeboard (Bacheca)
# ---------------------------------------------------------------------------


class ClasseVivaNoticeboardSensor(ClasseVivaBaseSensor):
    """Noticeboard notice counter sensor."""

    _attr_name = "Noticeboard Notices"
    _attr_icon = "mdi:bulletin-board"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "notices"

    def __init__(self, coordinator: ClasseVivaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "noticeboard")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("noticeboard", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self.coordinator.data.get("noticeboard", [])
        unread = [i for i in items if not i.get("readStatus", False)]
        return {
            "unread_count": len(unread),
            "notices": [
                {
                    "title": i.get("cntTitle"),
                    "author": i.get("cntAuthor"),
                    "category": i.get("cntCategory"),
                    "begin": i.get("evtBegin"),
                    "read": i.get("readStatus", False),
                    "has_attachment": bool(i.get("attachments")),
                }
                for i in items
            ],
        }


# ---------------------------------------------------------------------------
# Didactics (Area didattica)
# ---------------------------------------------------------------------------


class ClasseVivaDidacticsSensor(ClasseVivaBaseSensor):
    """Didactics item counter sensor (area didattica)."""

    _attr_name = "Didactics Items"
    _attr_icon = "mdi:book-open-variant"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "items"

    def __init__(self, coordinator: ClasseVivaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "didactics")

    @property
    def native_value(self) -> int:
        teachers = self.coordinator.data.get("didactics", [])
        count = 0
        for teacher in teachers:
            for folder in teacher.get("folders", []):
                count += len(folder.get("agendaItems", []))
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        teachers = self.coordinator.data.get("didactics", [])
        folders: list[dict] = []
        items: list[dict] = []
        for teacher in teachers:
            teacher_name = teacher.get("teacherName")
            for folder in teacher.get("folders", []):
                folder_name = folder.get("folderName")
                folders.append(
                    {
                        "teacher": teacher_name,
                        "folder": folder_name,
                        "items": len(folder.get("agendaItems", [])),
                        "last_updated": folder.get("lastShareDt"),
                    }
                )
                for item in folder.get("agendaItems", []):
                    items.append(
                        {
                            "teacher": teacher_name,
                            "folder": folder_name,
                            "item_id": item.get("itemId") or item.get("contentId"),
                            "name": item.get("displayName") or item.get("itemName"),
                            "share_date": item.get("shareDt"),
                            "local_url": item.get("local_url"),
                        }
                    )
        return {"folders": folders, "items": items}


# ---------------------------------------------------------------------------
# Next agenda event
# ---------------------------------------------------------------------------


class ClasseVivaNextAgendaSensor(ClasseVivaBaseSensor):
    """Sensor showing the next upcoming agenda event."""

    _attr_name = "Next Agenda Event"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: ClasseVivaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_agenda")

    @property
    def native_value(self) -> str | None:
        """Return the notes/description of the next agenda event."""
        events = sorted(
            self.coordinator.data.get("agenda", []),
            key=lambda e: e.get("evtDatetimeBegin", ""),
        )
        if not events:
            return None
        next_event = events[0]
        return next_event.get("notes") or next_event.get("subjectDesc") or "Event"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        events = sorted(
            self.coordinator.data.get("agenda", []),
            key=lambda e: e.get("evtDatetimeBegin", ""),
        )
        next_event_attrs: dict[str, Any] = {}
        if events:
            e = events[0]
            next_event_attrs = {
                "begin": e.get("evtDatetimeBegin"),
                "end": e.get("evtDatetimeEnd"),
                "subject": e.get("subjectDesc"),
                "author": e.get("authorName"),
                "type": e.get("evtCode"),
                "full_day": e.get("isFullDay"),
                "student_relevant": e.get("student_relevant", False),
            }
        # Expose the next 10 upcoming events so the dashboard card can show
        # a full list without requiring extra API calls.
        upcoming = [
            {
                "begin": e.get("evtDatetimeBegin"),
                "end": e.get("evtDatetimeEnd"),
                "subject": e.get("subjectDesc"),
                "notes": e.get("notes"),
                "author": e.get("authorName"),
                "type": e.get("evtCode"),
                "full_day": e.get("isFullDay"),
                "student_relevant": e.get("student_relevant", False),
            }
            for e in events[:10]
        ]
        return {**next_event_attrs, "upcoming_events": upcoming}
