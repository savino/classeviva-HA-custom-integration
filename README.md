# ClasseViva – Home Assistant Custom Integration

A [Home Assistant](https://www.home-assistant.io/) custom integration for the
**Spaggiari / ClasseViva** school portal (`web.spaggiari.eu`).

## Features

| Feature | Details |
|---|---|
| **Grades** | Average grade sensor with the 10 most recent grades as attributes |
| **Absences** | Count of unjustified absences with full list in attributes |
| **Noticeboard (Bacheca)** | Count of notices with unread count highlighted |
| **Didactics (Area Didattica)** | Count of educational items; new attachments are **auto-downloaded** and served locally; download link available in sensor attributes and in the dashboard card |
| **Next Agenda Event** | Sensor showing the next 10 upcoming events, with a `student_relevant` flag when the student's name is mentioned |
| **Calendar** | Full agenda exposed as a Home Assistant calendar entity (compatible with iCal) |
| **Notifications** | Home Assistant events fired whenever new content is detected (usable in automations) |
| **Dashboard card** | Custom Lovelace card showing grades, noticeboard notices, agenda events and didactic materials in one place |

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations → Custom repositories**.
3. Add `https://github.com/savino/classeviva-HA-custom-integration` with category **Integration**.
4. Search for **ClasseViva** and install it.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/classeviva` folder into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **ClasseViva**.
3. Enter your **ClasseViva username** (or email) and **password**.
4. The integration will create a device with all sensor and calendar entities.

Multiple student accounts can be configured simultaneously.

## Entities

### Sensors

| Entity | State | Attributes |
|---|---|---|
| `sensor.<name>_average_grade` | Numeric average of all grades | `recent_grades` list |
| `sensor.<name>_unjustified_absences` | Count | `absences` list, `total_absences` |
| `sensor.<name>_noticeboard_notices` | Total count | `unread_count`, `notices` list |
| `sensor.<name>_didactics_items` | Total item count | `folders` list, `items` list (each with `local_url`) |
| `sensor.<name>_next_agenda_event` | Event summary | `begin`, `end`, `subject`, `author`, `type`, `student_relevant`, `upcoming_events` (next 10) |

### Calendar

`calendar.<name>_agenda` – shows all agenda events for the next 30 days.

You can subscribe to this calendar from any iCal-compatible client via the
Home Assistant **Calendar** integration's export URL, or use the built-in
**Calendar** dashboard card.

## Dashboard Card (Lovelace)

The integration provides a custom Lovelace card that shows grades, noticeboard
notices, upcoming agenda events (with student-relevant ones highlighted) and
didactic materials with download links.

### Register the card resource

Add the following to your Lovelace **Resources** (Settings → Dashboards → ⋮ → Resources):

| URL | Type |
|---|---|
| `/classeviva_card/classeviva-card.js` | JavaScript module |

### Card configuration

```yaml
type: custom:classeviva-card
title: "Mario Rossi – ClasseViva"
grades_entity: sensor.average_grade
noticeboard_entity: sensor.noticeboard_notices
agenda_entity: sensor.next_agenda_event
didactics_entity: sensor.didactics_items
```

All four entity properties are optional – omit any section you don't need.

## Didactic content local storage

When new files are detected in the *Area Didattica*, the integration
automatically downloads them and stores them in:

```
<config>/www/classeviva_didactics/<item_id>/<filename>
```

Files are accessible in the browser at `/local/classeviva_didactics/…` and the
download URL is exposed in `sensor.<name>_didactics_items` attributes
(`items[*].local_url`).

Files older than **60 days** are removed automatically on every poll.  You can
also trigger an immediate cleanup via the service call:

```yaml
service: classeviva.cleanup_didactics_storage
```

## Home Assistant Events (Notifications)

The integration fires Home Assistant bus events whenever **new** content is
detected during a poll. You can use these events in automations to send push
notifications, emails, etc.

| Event | Fired when | Event data fields |
|---|---|---|
| `classeviva_new_didactics` | New file/link in Area Didattica | `teacher`, `folder`, `item_name`, `share_date` |
| `classeviva_new_noticeboard` | New notice on the Bacheca | `title`, `author`, `category`, `begin` |
| `classeviva_new_agenda` | New entry in the student's agenda | `notes`, `author`, `subject`, `begin`, `end` |
| `classeviva_student_agenda_event` | New agenda event that mentions the student's last name | `notes`, `author`, `subject`, `begin`, `end` |

### Example automation – push notification on new notice

```yaml
automation:
  - alias: "Notify new ClasseViva notice"
    trigger:
      - platform: event
        event_type: classeviva_new_noticeboard
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "New notice on ClasseViva"
          message: "{{ trigger.event.data.title }} — {{ trigger.event.data.author }}"
```

### Example automation – notify when an agenda event specifically mentions the student

```yaml
automation:
  - alias: "Notify personal agenda event"
    trigger:
      - platform: event
        event_type: classeviva_student_agenda_event
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Agenda – evento personale"
          message: "{{ trigger.event.data.subject }}: {{ trigger.event.data.notes }}"
```

## Update Interval

Data is refreshed every **60 minutes** by default. This is intentional to
avoid overloading the Spaggiari servers. If you need faster updates you can
call the `homeassistant.update_entity` service on the relevant entities.

## Supported API Endpoints

The integration calls the following Spaggiari REST API endpoints:

- `POST /auth/login/` – authentication
- `GET /students/{id}/grades` – grades
- `GET /students/{id}/absences/details` – absences
- `GET /students/{id}/agenda/all/{begin}/{end}` – agenda (30-day window)
- `GET /students/{id}/didactics` – area didattica
- `GET /students/{id}/noticeboard` – bacheca
- `GET /students/{id}/didactics/item/{contentId}` – didactic attachment download

## License

This project is licensed under the [Apache 2.0 License](LICENSE).
