"""Tests for the ClasseViva async API client."""
from __future__ import annotations

from http.cookies import SimpleCookie
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.classeviva.api import AuthenticationError, ClasseVivaAPI
from custom_components.classeviva.const import AUTH_URL, BASE_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(
    data: dict,
    *,
    status: int = 200,
    cookies: dict[str, str] | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.cookies = SimpleCookie()
    for name, value in (cookies or {}).items():
        response.cookies[name] = value
    response.json = AsyncMock(return_value=data)
    response.read = AsyncMock(return_value=b"file")
    response.headers = {"Content-Type": "application/json"}
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


def _api_with_cookies(session: MagicMock) -> ClasseVivaAPI:
    """Return an API instance with a current w1 session."""
    api = ClasseVivaAPI("u", "p", session, school_code="school")
    api._cookies = {"PHPSESSID": "sid", "webidentity": "S1", "webrole": "gen"}
    api._student_id = "13000000"
    return api


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_uses_form_cookies_and_whoami():
    """Login uses documented form fields and resolves the numeric student ID."""
    session = MagicMock()
    session.post = MagicMock(
        return_value=_response(
            {},
            cookies={"PHPSESSID": "sid", "webidentity": "S12345", "webrole": "gen"},
        )
    )
    session.get = MagicMock(return_value=_response({
        "id": "13000000", "nome": "MARIO", "cognome": "ROSSI"
    }))
    api = ClasseVivaAPI("student", "secret", session, "school", "1234", "genitori")
    info = await api.login()

    session.post.assert_called_once_with(
        AUTH_URL,
        data={
            "uid": "student",
            "pwd": "secret",
            "cid": "school",
            "target": "genitori",
            "pin": "1234",
        },
    )
    whoami_call = session.get.call_args
    assert whoami_call.args[0] == f"{BASE_URL}/misc/whoami"
    assert whoami_call.kwargs["cookies"]["PHPSESSID"] == "sid"
    assert info == {"id": "13000000", "first_name": "MARIO", "last_name": "ROSSI"}


@pytest.mark.asyncio
async def test_login_accepts_verified_php_session_without_optional_fields():
    """Password-only login may return PHPSESSID and the school code in its payload."""
    session = MagicMock()
    session.post = MagicMock(
        return_value=_response(
            {
                "data": {
                    "auth": {
                        "verified": True,
                        "loggedIn": True,
                        "accountInfo": {"cid": "school"},
                    }
                }
            },
            cookies={"PHPSESSID": "sid"},
        )
    )
    session.get = MagicMock(return_value=_response({
        "id": "13000000", "nome": "MARIO", "cognome": "ROSSI"
    }))
    api = ClasseVivaAPI("student", "secret", session)

    info = await api.login()

    session.post.assert_called_once_with(
        AUTH_URL,
        data={"uid": "student", "pwd": "secret"},
    )
    assert session.get.call_args.kwargs["cookies"] == {"PHPSESSID": "sid"}
    assert api._school_code == "school"
    assert info == {"id": "13000000", "first_name": "MARIO", "last_name": "ROSSI"}


@pytest.mark.asyncio
async def test_login_failure():
    """login() raises AuthenticationError on bad credentials."""
    session = MagicMock()
    session.post = MagicMock(return_value=_response({"error": "authentication failed"}))
    api = ClasseVivaAPI("bad", "creds", session, "school")

    with pytest.raises(AuthenticationError):
        await api.login()


@pytest.mark.asyncio
async def test_grades_uses_current_school_year_endpoint():
    """Grades route includes the current academic year suffix."""
    session = MagicMock()
    session.get = MagicMock(return_value=_response({"grades": [{"evtId": 1}]}))
    api = _api_with_cookies(session)

    grades = await api.grades()
    today = datetime.now()
    year_start = today.year if today.month >= 9 else today.year - 1
    assert session.get.call_args.args[0] == (
        f"{BASE_URL}/students/13000000/grades{year_start % 100:02d}"
    )
    assert grades == [{"evtId": 1}]


@pytest.mark.asyncio
async def test_absences_and_agenda_use_documented_routes():
    session = MagicMock()
    session.get = MagicMock(side_effect=[
        _response({"events": [{"evtId": 1}]}),
        _response({"agenda": [{"evtId": 2}]}),
    ])
    api = _api_with_cookies(session)

    assert await api.absences() == [{"evtId": 1}]
    assert await api.agenda(datetime(2025, 9, 1), datetime(2026, 6, 30)) == [{"evtId": 2}]
    assert session.get.call_args_list[0].args[0] == (
        f"{BASE_URL}/students/13000000/absences/details"
    )
    assert session.get.call_args_list[1].args[0] == (
        f"{BASE_URL}/students/13000000/agendav2/all/20250901/20260630"
    )


@pytest.mark.asyncio
async def test_noticeboard():
    """noticeboard() returns items list."""
    nb_resp = {
        "items": [
            {"pubId": 10, "cntTitle": "Avviso", "cntAuthor": "Preside", "readStatus": False}
        ]
    }
    session = MagicMock()
    session.get = MagicMock(return_value=_response(nb_resp))
    api = _api_with_cookies(session)

    items = await api.noticeboard()
    assert len(items) == 1
    assert items[0]["cntTitle"] == "Avviso"


@pytest.mark.asyncio
async def test_didactics_normalizes_documented_contents():
    """Didactics handles the upstream typo and normalizes current content fields."""
    did_resp = {"didacticts": [{
        "teacherName": "Prof. Bianchi",
        "folders": [{
            "folderName": "Materiali",
            "lastShareDT": "2026-09-10T10:00:00+02:00",
            "contents": [{
                "contentId": 10,
                "contentName": "Dispensa",
                "objectId": 20,
                "objectType": "file",
                "shareDT": "2026-09-10T10:00:00+02:00",
            }],
        }],
    }]}
    session = MagicMock()
    session.get = MagicMock(return_value=_response(did_resp))
    api = _api_with_cookies(session)

    result = await api.didactics()
    assert result[0]["teacherName"] == "Prof. Bianchi"
    folder = result[0]["folders"][0]
    assert folder["agendaItems"][0]["itemName"] == "Dispensa"
    assert folder["agendaItems"][0]["shareDt"] == "2026-09-10T10:00:00+02:00"
    assert folder["lastShareDt"] == "2026-09-10T10:00:00+02:00"
