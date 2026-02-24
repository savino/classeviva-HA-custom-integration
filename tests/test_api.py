"""Tests for the ClasseViva async API client."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.classeviva.api import AuthenticationError, ClasseVivaAPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(responses: list[dict[str, Any]]) -> tuple[MagicMock, MagicMock]:
    """Return a (session, ctx) pair whose json() cycles through *responses*."""
    session = MagicMock()
    call_idx = [0]

    async def _json(**kwargs: Any) -> dict[str, Any]:
        data = responses[min(call_idx[0], len(responses) - 1)]
        call_idx[0] += 1
        return data

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=ctx)
    ctx.__aexit__ = AsyncMock(return_value=False)
    ctx.json = _json

    session.post = MagicMock(return_value=ctx)
    session.get = MagicMock(return_value=ctx)
    return session, ctx


def _api_with_token(session: MagicMock) -> ClasseVivaAPI:
    """Return a pre-authenticated API instance."""
    api = ClasseVivaAPI("u", "p", session)
    api._token = "tok"
    api._student_id = "1"
    return api


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success():
    """login() stores token and returns student info."""
    login_resp = {
        "token": "tok123",
        "ident": "S12345",
        "firstName": "Mario",
        "lastName": "Rossi",
    }
    session, _ = _make_session([login_resp])
    api = ClasseVivaAPI("user@example.com", "secret", session)
    info = await api.login()

    assert info["id"] == "12345"
    assert info["first_name"] == "Mario"
    assert info["last_name"] == "Rossi"
    assert api._token == "tok123"


@pytest.mark.asyncio
async def test_login_failure():
    """login() raises AuthenticationError on bad credentials."""
    login_resp = {"error": "authentication failed"}
    session, _ = _make_session([login_resp])
    api = ClasseVivaAPI("bad", "creds", session)

    with pytest.raises(AuthenticationError):
        await api.login()


@pytest.mark.asyncio
async def test_grades():
    """grades() returns the list from the API."""
    grades_resp = {
        "grades": [
            {"evtId": 1, "subjectDesc": "Math", "decimalValue": 8.0, "displayValue": "8"},
        ]
    }
    session, _ = _make_session([grades_resp])
    api = _api_with_token(session)

    grades = await api.grades()
    assert len(grades) == 1
    assert grades[0]["subjectDesc"] == "Math"


@pytest.mark.asyncio
async def test_noticeboard():
    """noticeboard() returns items list."""
    nb_resp = {
        "items": [
            {"pubId": 10, "cntTitle": "Avviso", "cntAuthor": "Preside", "readStatus": False}
        ]
    }
    session, _ = _make_session([nb_resp])
    api = _api_with_token(session)

    items = await api.noticeboard()
    assert len(items) == 1
    assert items[0]["cntTitle"] == "Avviso"


@pytest.mark.asyncio
async def test_didactics_typo_key():
    """didactics() handles the API typo 'didacticts'."""
    did_resp = {"didacticts": [{"teacherName": "Prof. Bianchi", "folders": []}]}
    session, _ = _make_session([did_resp])
    api = _api_with_token(session)

    result = await api.didactics()
    assert result[0]["teacherName"] == "Prof. Bianchi"
