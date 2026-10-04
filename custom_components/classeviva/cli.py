"""Command-line client for the ClasseViva API."""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

import aiohttp

from .api import AuthenticationError, ClasseVivaAPI


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 date or datetime supplied on the command line."""
    try:
        return datetime.fromisoformat(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(
            f"invalid ISO 8601 date or datetime: {value}"
        ) from err


def _load_settings(path: Path) -> dict[str, str]:
    """Load optional credentials from a local JSON settings file."""
    if not path.exists():
        return {}

    settings = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError("settings file must contain a JSON object")

    credentials: dict[str, str] = {}
    aliases = {
        "username": ("username",),
        "password": ("password",),
        "school_code": ("school_code", "cid", "id"),
        "pin": ("pin",),
        "target": ("target",),
    }
    for key, names in aliases.items():
        value = ""
        for name in names:
            candidate = settings.get(name)
            if candidate is not None:
                value = candidate
                break
        if not isinstance(value, str):
            raise ValueError(f"settings field '{key}' must be a string")
        credentials[key] = value
    return credentials


def build_parser() -> argparse.ArgumentParser:
    """Build the terminal client's argument parser."""
    parser = argparse.ArgumentParser(prog="classeviva")
    parser.add_argument(
        "--username",
        help="ClasseViva username (or set CLASSEVIVA_USERNAME)",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path(".classeviva.local.json"),
        help="credentials settings file (default: .classeviva.local.json)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("grades", "absences", "didactics", "noticeboard"):
        commands.add_parser(name, help=f"fetch {name}")

    agenda = commands.add_parser("agenda", help="fetch agenda events")
    agenda.add_argument("--begin", type=_parse_datetime, help="start date (ISO 8601)")
    agenda.add_argument("--end", type=_parse_datetime, help="end date (ISO 8601)")

    download = commands.add_parser("download", help="download a didactic attachment")
    download.add_argument("content_id", help="attachment content ID")
    download.add_argument(
        "--output",
        type=Path,
        help="destination file (default: classeviva-<content_id>.bin)",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    settings = _load_settings(args.settings)
    username = (
        args.username
        or os.environ.get("CLASSEVIVA_USERNAME")
        or settings.get("username")
    )
    if not username:
        username = input("ClasseViva username: ")

    password = os.environ.get("CLASSEVIVA_PASSWORD") or settings.get("password")
    if not password:
        password = getpass.getpass("ClasseViva password: ")
    school_code = os.environ.get("CLASSEVIVA_CID") or settings.get("school_code", "")
    pin = os.environ.get("CLASSEVIVA_PIN") or settings.get("pin", "")
    target = os.environ.get("CLASSEVIVA_TARGET") or settings.get("target") or None

    async with aiohttp.ClientSession() as session:
        api = ClasseVivaAPI(
            username,
            password,
            session,
            school_code=school_code,
            pin=pin,
            target=target,
        )
        await api.login()

        if args.command == "grades":
            result = await api.grades()
        elif args.command == "absences":
            result = await api.absences()
        elif args.command == "agenda":
            begin = args.begin or datetime.now()
            end = args.end or begin + timedelta(days=30)
            if end <= begin:
                raise ValueError("agenda end date must be after begin date")
            result = await api.agenda(begin, end)
        elif args.command == "didactics":
            result = await api.didactics()
        elif args.command == "noticeboard":
            result = await api.noticeboard()
        else:
            result = await api.download_didactic_content(args.content_id)
            if result is None:
                raise RuntimeError(f"attachment {args.content_id} is unavailable")
            output = args.output or Path(f"classeviva-{args.content_id}.bin")
            output.write_bytes(result)
            print(output)
            return 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the terminal client and return its process exit code."""
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (
        aiohttp.ClientError,
        AuthenticationError,
        EOFError,
        OSError,
        RuntimeError,
        ValueError,
    ) as err:
        print(f"classeviva: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())