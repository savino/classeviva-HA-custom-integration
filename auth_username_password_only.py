"""Manually probe ClasseViva authentication with only username and password.

Run from the project root with:
    python auth_username_password_only.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Sequence

import aiohttp


AUTH_URL = (
    "https://web.spaggiari.eu/auth-p7/app/default/"
    "AuthApi4.php?a=aLoginPwd"
)
BASE_URL = "https://web.spaggiari.eu/rest/w1"
DEFAULT_SETTINGS = (
    Path(__file__).resolve().parent / ".classeviva.local.json"
)


def _read_credentials(path: Path) -> tuple[str, str]:
    """Read only username and password from the local JSON settings."""
    if not path.is_file():
        raise ValueError(f"settings file not found: {path}")

    settings = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError("settings file must contain a JSON object")

    username = settings.get("username")
    password = settings.get("password")
    if not isinstance(username, str) or not username:
        raise ValueError("settings file must contain a non-empty 'username'")
    if not isinstance(password, str) or not password:
        raise ValueError("settings file must contain a non-empty 'password'")
    return username, password


async def _authenticate(
    username: str, password: str
) -> tuple[int, set[str], bool, bool, bool, int | None, bool]:
    """Submit exactly uid and pwd and verify the returned session with whoami."""
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            AUTH_URL,
            data={"uid": username, "pwd": password},
        ) as response:
            status = response.status
            cookies = {name: cookie.value for name, cookie in response.cookies.items()}
            try:
                payload = await response.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError):
                payload = {}

        auth = payload.get("data", {}).get("auth", {}) if isinstance(payload, dict) else {}
        verified = isinstance(auth, dict) and auth.get("verified") is True
        logged_in = isinstance(auth, dict) and auth.get("loggedIn") is True
        account_info = auth.get("accountInfo", {}) if isinstance(auth, dict) else {}
        school_code_present = (
            isinstance(account_info, dict) and bool(account_info.get("cid"))
        )

        whoami_status = None
        whoami_has_id = False
        if status < 400 and cookies and verified and logged_in:
            async with session.get(
                f"{BASE_URL}/misc/whoami",
                cookies=cookies,
            ) as response:
                whoami_status = response.status
                try:
                    whoami = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    whoami = {}
            whoami_has_id = (
                whoami_status == 200
                and isinstance(whoami, dict)
                and bool(whoami.get("id"))
            )

        return (
            status,
            set(cookies),
            verified,
            logged_in,
            school_code_present,
            whoami_status,
            whoami_has_id,
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the manual authentication probe argument parser."""
    parser = argparse.ArgumentParser(
        description="Probe ClasseViva login using only username and password."
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS,
        help=f"credentials JSON file (default: {DEFAULT_SETTINGS})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the direct authentication request and print a sanitized result."""
    args = build_parser().parse_args(argv)
    try:
        username, password = _read_credentials(args.settings)
        (
            status,
            cookie_names,
            verified,
            logged_in,
            school_code_present,
            whoami_status,
            whoami_has_id,
        ) = asyncio.run(_authenticate(username, password))
    except (aiohttp.ClientError, OSError, ValueError, json.JSONDecodeError) as err:
        print(f"Authentication probe failed: {err}", file=sys.stderr)
        return 1

    print(f"HTTP status: {status}")
    print("Returned cookie names:", ", ".join(sorted(cookie_names)) or "none")
    print(f"Server verified credentials: {verified}")
    print(f"Server reports logged in: {logged_in}")
    print(f"School code returned by server: {school_code_present}")
    if whoami_status is not None:
        print(f"whoami HTTP status: {whoami_status}")
        print(f"whoami returned student ID: {whoami_has_id}")
    if status < 400 and verified and logged_in and whoami_has_id:
        print("Username/password-only login and authenticated session confirmed.")
        return 0

    print(
        "Login was not confirmed by an authenticated whoami request. "
        "Check the HTTP status and server verification fields above."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
