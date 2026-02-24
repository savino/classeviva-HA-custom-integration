"""Tests for the DidacticsStorage local-file manager."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from custom_components.classeviva.storage import DidacticsStorage, _TS_FILE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _storage(tmp_path: Path) -> DidacticsStorage:
    """Return a DidacticsStorage rooted at *tmp_path* (acts as the www dir)."""
    return DidacticsStorage(tmp_path)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_and_has_content(tmp_path: Path) -> None:
    """save_content() writes the file; has_content() detects it."""
    s = _storage(tmp_path)
    assert not s.has_content(1)

    saved = s.save_content(1, "notes.pdf", b"PDF data")
    assert saved.exists()
    assert saved.read_bytes() == b"PDF data"
    assert s.has_content(1)


def test_get_content_path_returns_file(tmp_path: Path) -> None:
    """get_content_path() returns the actual content file, not the timestamp."""
    s = _storage(tmp_path)
    s.save_content(42, "homework.docx", b"\x00\x01")
    path = s.get_content_path(42)
    assert path is not None
    assert path.name == "homework.docx"


def test_get_content_path_missing(tmp_path: Path) -> None:
    """get_content_path() returns None when nothing is stored."""
    s = _storage(tmp_path)
    assert s.get_content_path(99) is None


def test_local_url(tmp_path: Path) -> None:
    """local_url() returns the /local/ URL for a cached item."""
    s = _storage(tmp_path)
    s.save_content(7, "slides.pptx", b"data")
    url = s.local_url(7)
    assert url == "/local/classeviva_didactics/7/slides.pptx"


def test_local_url_missing(tmp_path: Path) -> None:
    """local_url() returns None when nothing is cached."""
    s = _storage(tmp_path)
    assert s.local_url(7) is None


def test_cleanup_removes_old_items(tmp_path: Path) -> None:
    """cleanup_old_content() removes items whose timestamp is older than max_age."""
    s = _storage(tmp_path)
    s.save_content(1, "old.pdf", b"old")
    s.save_content(2, "new.pdf", b"new")

    # Back-date item 1's timestamp to 61 days ago
    ts_file = tmp_path / "classeviva_didactics" / "1" / _TS_FILE
    old_ts = _utcnow() - timedelta(days=61)
    ts_file.write_text(old_ts.isoformat())

    removed = s.cleanup_old_content(max_age_days=60)

    assert removed == 1
    assert not s.has_content(1)
    assert s.has_content(2)


def test_cleanup_keeps_recent_items(tmp_path: Path) -> None:
    """cleanup_old_content() does not remove items within the retention window."""
    s = _storage(tmp_path)
    s.save_content(10, "recent.pdf", b"data")

    removed = s.cleanup_old_content(max_age_days=60)
    assert removed == 0
    assert s.has_content(10)


def test_cleanup_empty_storage(tmp_path: Path) -> None:
    """cleanup_old_content() returns 0 when storage is empty."""
    s = _storage(tmp_path)
    assert s.cleanup_old_content() == 0


def test_overwrite_updates_timestamp(tmp_path: Path) -> None:
    """Saving the same item again updates the timestamp file."""
    s = _storage(tmp_path)
    s.save_content(5, "file.txt", b"v1")
    ts_file = tmp_path / "classeviva_didactics" / "5" / _TS_FILE
    first_ts = datetime.fromisoformat(ts_file.read_text())

    # Small sleep to ensure time advances
    time.sleep(0.05)
    s.save_content(5, "file.txt", b"v2")
    second_ts = datetime.fromisoformat(ts_file.read_text())

    assert second_ts >= first_ts
    path = s.get_content_path(5)
    assert path is not None
    assert path.read_bytes() == b"v2"
