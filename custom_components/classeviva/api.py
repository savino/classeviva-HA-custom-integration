"""Async API client for the Spaggiari / ClasseViva REST API."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import aiohttp

from .const import BASE_URL


class AuthenticationError(Exception):
    """Raised when login credentials are invalid."""


class ClasseVivaAPI:
    """Thin async wrapper around the Spaggiari REST API."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._token: str | None = None
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
        headers = {
            "User-Agent": "zorro/1.0",
            "Z-Dev-Apikey": "+zorro+",
            "Content-Type": "application/json",
        }
        async with self._session.post(
            f"{BASE_URL}/auth/login/",
            json={"uid": self._username, "pass": self._password},
            headers=headers,
        ) as resp:
            data = await resp.json(content_type=None)

        if "authentication failed" in data.get("error", "").lower():
            raise AuthenticationError("Invalid username or password")

        self._token = data["token"]
        self._student_id = re.sub(r"\D", "", data["ident"])
        self.first_name = data["firstName"]
        self.last_name = data["lastName"]

        return {
            "id": self._student_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_student_url(self) -> str:
        return f"{BASE_URL}/students/{self._student_id}"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "User-Agent": "zorro/1.0",
            "Z-Dev-Apikey": "+zorro+",
            "Z-Auth-Token": self._token or "",
        }

    async def _get(self, *path_segments: str) -> Any:
        """Perform a GET request, refreshing the token if expired."""
        url = self._base_student_url() + "/" + "/".join(path_segments)
        async with self._session.get(url, headers=self._auth_headers()) as resp:
            data = await resp.json(content_type=None)

        if "auth token expired" in data.get("error", "").lower():
            await self.login()
            return await self._get(*path_segments)

        return data

    async def _post(self, *path_segments: str) -> Any:
        """Perform a POST request, refreshing the token if expired."""
        url = self._base_student_url() + "/" + "/".join(path_segments)
        async with self._session.post(url, headers=self._auth_headers()) as resp:
            data = await resp.json(content_type=None)

        if "auth token expired" in data.get("error", "").lower():
            await self.login()
            return await self._post(*path_segments)

        return data

    @staticmethod
    def _fmt_date(dt: datetime) -> str:
        return dt.strftime("%Y%m%d")

    # ------------------------------------------------------------------
    # Data endpoints
    # ------------------------------------------------------------------

    async def grades(self) -> list[dict]:
        """Return the student's grades."""
        data = await self._get("grades")
        return data.get("grades", [])

    async def absences(self) -> list[dict]:
        """Return the student's absences."""
        data = await self._get("absences", "details")
        return data.get("events", [])

    async def agenda(self, begin: datetime, end: datetime) -> list[dict]:
        """Return the student's agenda events between *begin* and *end*."""
        data = await self._get(
            "agenda", "all", self._fmt_date(begin), self._fmt_date(end)
        )
        return data.get("agenda", [])

    async def didactics(self) -> list[dict]:
        """Return the student's educational content (area didattica)."""
        data = await self._get("didactics")
        # The API key has a typo in some versions
        return data.get("didacticts", data.get("didactics", []))

    async def noticeboard(self) -> list[dict]:
        """Return the student's noticeboard (bacheca)."""
        data = await self._get("noticeboard")
        return data.get("items", [])

    async def download_didactic_content(self, content_id: int | str) -> bytes | None:
        """Download the binary content of a didactic attachment.

        Returns raw bytes on success, or ``None`` if the content is unavailable.
        Re-authenticates once if the token has expired.
        """
        url = self._base_student_url() + f"/didactics/item/{content_id}"
        async with self._session.get(url, headers=self._auth_headers()) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if resp.status == 200 and "application/json" not in content_type:
                return await resp.read()
            # Try to parse error payload; handle token expiry
            try:
                data = await resp.json(content_type=None)
            except Exception:  # noqa: BLE001
                return None
            if "auth token expired" in data.get("error", "").lower():
                await self.login()
                return await self.download_didactic_content(content_id)
            return None
