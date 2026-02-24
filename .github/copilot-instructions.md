# Copilot instructions for classeviva-HA-custom-integration

## Project shape and data flow
- This is a Home Assistant custom integration under `custom_components/classeviva` with config-entry setup (`__init__.py`) and two platforms: `sensor` and `calendar` (`const.py` -> `PLATFORMS`).
- Runtime flow is: config flow validates credentials (`config_flow.py`) -> API client login (`api.py`) -> `ClasseVivaCoordinator` fetches all endpoint data (`coordinator.py`) -> entities read only from `coordinator.data` (`sensor.py`, `calendar.py`).
- Keep new entity logic coordinator-driven; avoid direct API calls from entities.

## API/client conventions
- `ClasseVivaAPI` is a thin async wrapper using shared aiohttp session from HA (`async_get_clientsession`).
- Authentication details are Spaggiari-specific headers (`User-Agent: zorro/1.0`, `Z-Dev-Apikey: +zorro+`) and token in `Z-Auth-Token` (`api.py`).
- Preserve token-expiry retry behavior in `_get`/`_post`: on `"auth token expired"`, call `login()` and retry once via recursion.
- Preserve known upstream quirk: didactics may arrive under `didacticts` (typo) or `didactics` (`api.py::didactics`).

## Coordinator/event behavior
- `ClasseVivaCoordinator` polls grades, absences, agenda (30-day lookahead), didactics, noticeboard in a single `_async_update_data` call.
- Event notifications (`classeviva_new_*`) are emitted only after initial baseline fetch; first refresh intentionally does not fire events (`coordinator.py`).
- “New content” detection is ID-set based:
  - Didactics: `itemId` fallback `contentId`
  - Noticeboard: `pubId`
  - Agenda: `evtId`
- If adding new notifications, follow same pattern: collect stable IDs, skip first fetch, fire HA bus events from coordinator.

## Entity modeling patterns
- Sensors/calendar use `CoordinatorEntity` and share `device_info` identifiers `(DOMAIN, entry_id)` so all entities group under one device.
- Unique IDs are entry-scoped (`f"{entry.entry_id}_{key}"`), which allows multiple student accounts.
- Sensor attributes expose curated API fields (e.g., last 10 grades, unread notice count) rather than raw payload dumps.
- Calendar conversion must tolerate malformed times and enforce `end > start` (`calendar.py::_raw_to_event`).

## Development workflow for this repo
- Tests are lightweight unit tests focused on API client behavior in `tests/test_api.py`.
- Home Assistant is intentionally stubbed in `tests/conftest.py`; do not assume a full HA runtime in tests.
- Run tests with:
  - `pip install -r requirements_test.txt`
  - `pytest`
- Keep changes compatible with the current minimal dependency model (`manifest.json` has empty `requirements`).

## Change guidance for AI agents
- Prefer minimal, surgical changes in existing files; keep naming and docstring style consistent.
- When adding API parsing, use `.get(...)` patterns and defensive fallbacks as done throughout `api.py`/`sensor.py`.
- When adding coordinator data keys, update all readers (`sensor.py`, `calendar.py`) and keep returned `coordinator.data` schema explicit.
- If behavior changes user-visible entities/events, update `README.md` sections for features/events accordingly.
