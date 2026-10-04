"""Tests for the standalone ClasseViva command-line client."""
from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

from custom_components.classeviva.cli import _load_settings


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_settings(tmp_path: Path) -> None:
    """Load credentials from a JSON file without exposing them in output."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({
            "username": "student",
            "password": "secret",
            "school_code": "school",
            "pin": "1234",
            "target": "studenti",
        }),
        encoding="utf-8",
    )

    assert _load_settings(settings_path) == {
        "username": "student",
        "password": "secret",
        "school_code": "school",
        "pin": "1234",
        "target": "studenti",
    }


def test_load_settings_accepts_legacy_aliases(tmp_path: Path) -> None:
    """Support older local-config names such as 'id' or 'cid'."""
    settings_path = tmp_path / "legacy-settings.json"
    settings_path.write_text(
        json.dumps({
            "username": "student",
            "password": "secret",
            "id": "legacy-school",
            "pin": "1234",
        }),
        encoding="utf-8",
    )

    assert _load_settings(settings_path) == {
        "username": "student",
        "password": "secret",
        "school_code": "legacy-school",
        "pin": "1234",
        "target": "",
    }


def test_api_and_cli_import_without_homeassistant() -> None:
    """The shared API and CLI modules do not require Home Assistant."""
    code = """
import importlib.abc
import sys

class BlockHomeAssistant(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "homeassistant" or fullname.startswith("homeassistant."):
            raise ModuleNotFoundError("Home Assistant is unavailable")
        return None

sys.meta_path.insert(0, BlockHomeAssistant())
from custom_components.classeviva.api import ClasseVivaAPI
from custom_components.classeviva.cli import build_parser

assert ClasseVivaAPI
assert build_parser().parse_args(["grades"]).command == "grades"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_cli_help() -> None:
    """The module entry point exposes endpoint and download commands."""
    result = subprocess.run(
        [sys.executable, "-m", "custom_components.classeviva.cli", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "grades" in result.stdout
    assert "download" in result.stdout