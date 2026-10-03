"""Async API client for the Spaggiari / ClasseViva REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import aiohttp

from .const import AUTH_URL, BASE_URL


class AuthenticationError(Exception):
    """Raised when login credentials are invalid."""


class ClasseVivaAPI:
    """Thin async wrapper around the Spaggiari REST API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        school_code: str = "",
        pin: str = "",
        target: str = "genitori",
    ) -> None:
        self._username = username
        self._password = password
        self._school_code = school_code
        self._pin = pin
        self._target = target
        self._session = session
        self._cookies: dict[str, str] = {}
        self._student_id: str | None = None
        self.first_name: str | None = None
        self.last_name: str | None = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(self) -> dict[str, Any]:
        """Authenticate and store the session token.

        Returns a dict with ``id``, ``first_name`` and ``last_name``.
        Raises :class:`AuthenticationError` on bad credentials.
        """
        self._cookies.clear()
        form = {
            "uid": self._username,
            "pwd": self._password,
            "cid": self._school_code,
            "target": self._target,
        }
        if self._pin:
            form["pin"] = self._pin

        async with self._session.post(AUTH_URL, data=form) as resp:
            self._cookies = {
                name: cookie.value for name, cookie in resp.cookies.items()
            }
            if resp.status >= 400 or not self._cookies.get("webidentity"):
                try:
                    data = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    data = {}
                if "authentication failed" in data.get("error", "").lower():
                    raise AuthenticationError("Invalid ClasseViva credentials")
                raise AuthenticationError("ClasseViva login did not return session cookies")

        data = await self._get("misc", "whoami", student=False, retry=False)
        if not data.get("id"):
            raise AuthenticationError("Invalid username or password")

        self._student_id = str(data["id"])
        self.first_name = data.get("nome") or data.get("firstName")
        self.last_name = data.get("cognome") or data.get("lastName")

        return {
            "id": self._student_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(
        self,
        *path_segments: str,
        student: bool = True,
        retry: bool = True,
    ) -> Any:
        """Perform a cookie-authenticated GET, refreshing an expired session once."""
        base_url = BASE_URL
        if student:
            if self._student_id is None:
                raise AuthenticationError("Student identity is not available")
            base_url += f"/students/{self._student_id}"
        url = base_url + "/" + "/".join(path_segments)
        async with self._session.get(url, cookies=self._cookies) as resp:
            status = resp.status
            data = await resp.json(content_type=None)

        expired = status in (401, 403) or "auth token expired" in data.get("error", "").lower()
        if expired and retry:
            await self.login()
            return await self._get(*path_segments, student=student, retry=False)
        if status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=resp.request_info,
                history=resp.history,
                status=status,
                message=str(data.get("error", "API request failed")),
                headers=resp.headers,
            )
        return data

    @staticmethod
    def _fmt_date(dt: datetime) -> str:
        return dt.strftime("%Y%m%d")

    # ------------------------------------------------------------------
    # Data endpoints
    # ------------------------------------------------------------------

    async def grades(self) -> list[dict]:
        """Return the student's grades."""
        now = datetime.now()
        school_year_start = now.year if now.month >= 9 else now.year - 1
        data = await self._get(f"grades{school_year_start % 100:02d}")
        return data.get("grades", [])

    async def absences(self) -> list[dict]:
        """Return the student's absences."""
        data = await self._get("absences", "details")
        return data.get("events", [])

    async def agenda(self, begin: datetime, end: datetime) -> list[dict]:
        """Return the student's agenda events between *begin* and *end*."""
        data = await self._get(
            "agendav2", "all", self._fmt_date(begin), self._fmt_date(end)
        )
        return data.get("agenda", [])

    async def didactics(self) -> list[dict]:
        """Return the student's educational content (area didattica)."""
        data = await self._get("didactics")
        teachers = data.get("didacticts", data.get("didactics", []))
        for teacher in teachers:
            for folder in teacher.get("folders", []):
                folder.setdefault("lastShareDt", folder.get("lastShareDT"))
                contents = folder.get("contents", [])
                for item in contents:
                    item.setdefault("itemName", item.get("contentName"))
                    item.setdefault("shareDt", item.get("shareDT"))
                folder.setdefault("agendaItems", contents)
        return teachers

    async def noticeboard(self) -> list[dict]:
        """Return the student's noticeboard (bacheca)."""
        data = await self._get("noticeboard")
        return data.get("items", [])

    async def download_didactic_content(
        self, content_id: int | str, retry: bool = True
    ) -> bytes | None:
        """Download the binary content of a didactic attachment.

        Returns raw bytes on success, or ``None`` if the content is unavailable.
        Re-authenticates once if the token has expired.
        """
        if self._student_id is None:
            raise AuthenticationError("Student identity is not available")
        url = f"{BASE_URL}/students/{self._student_id}/didactics/item/{content_id}"
        async with self._session.get(url, cookies=self._cookies) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if resp.status == 200 and "application/json" not in content_type:
                return await resp.read()
            try:
                data = await resp.json(content_type=None)
            except Exception:  # noqa: BLE001
                return None
            if resp.status in (401, 403) or "auth token expired" in data.get("error", "").lower():
                if retry:
                    await self.login()
                    return await self.download_didactic_content(content_id, retry=False)
            return None
