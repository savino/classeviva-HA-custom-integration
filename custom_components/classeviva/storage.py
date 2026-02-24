"""Local storage manager for ClasseViva didactic content.

Downloaded files are kept under:
    <hass_config>/www/classeviva_didactics/<item_id>/<filename>

Because Home Assistant automatically serves everything under ``www/`` at the
``/local/`` URL prefix, clients can retrieve a file at::

    /local/classeviva_didactics/<item_id>/<filename>
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .const import DIDACTICS_STORAGE_SUBDIR

_LOGGER = logging.getLogger(__name__)

# Filename used to record when an item was first saved
_TS_FILE = ".cv_ts"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


class DidacticsStorage:
    """Manages locally cached copies of didactic attachment files."""

    def __init__(self, www_dir: Path) -> None:
        """Initialise the storage rooted at *www_dir*.

        ``www_dir`` should be the HA ``www`` directory (i.e.
        ``hass.config.path("www")``).  A ``classeviva_didactics`` sub-directory
        is created automatically.
        """
        self._root = Path(www_dir) / DIDACTICS_STORAGE_SUBDIR
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _item_dir(self, item_id: int | str) -> Path:
        return self._root / str(item_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_content(self, item_id: int | str) -> bool:
        """Return ``True`` if the item is already cached on disk."""
        d = self._item_dir(item_id)
        return d.exists() and any(f for f in d.iterdir() if f.name != _TS_FILE)

    def save_content(
        self,
        item_id: int | str,
        filename: str,
        data: bytes,
    ) -> Path:
        """Write *data* to disk and stamp its creation time.

        Returns the absolute :class:`~pathlib.Path` of the saved file.
        """
        d = self._item_dir(item_id)
        d.mkdir(parents=True, exist_ok=True)
        target = d / filename
        target.write_bytes(data)
        (d / _TS_FILE).write_text(_utcnow().isoformat())
        return target

    def get_content_path(self, item_id: int | str) -> Path | None:
        """Return the path of the cached file for *item_id*, or ``None``."""
        d = self._item_dir(item_id)
        if not d.exists():
            return None
        for f in d.iterdir():
            if f.name != _TS_FILE:
                return f
        return None

    def local_url(self, item_id: int | str) -> str | None:
        """Return the HA ``/local/`` URL for the cached file, or ``None``."""
        path = self.get_content_path(item_id)
        if path is None:
            return None
        return f"/local/{DIDACTICS_STORAGE_SUBDIR}/{item_id}/{path.name}"

    def cleanup_old_content(self, max_age_days: int = 60) -> int:
        """Remove items last saved more than *max_age_days* days ago.

        Returns the number of items (directories) removed.
        """
        if not self._root.exists():
            return 0
        cutoff = _utcnow() - timedelta(days=max_age_days)
        removed = 0
        for item_dir in list(self._root.iterdir()):
            if not item_dir.is_dir():
                continue
            ts_file = item_dir / _TS_FILE
            try:
                if ts_file.exists():
                    saved_at = datetime.fromisoformat(ts_file.read_text().strip())
                else:
                    saved_at = datetime.fromtimestamp(
                        item_dir.stat().st_mtime, tz=timezone.utc
                    ).replace(tzinfo=None)
                if saved_at < cutoff:
                    for f in item_dir.iterdir():
                        f.unlink(missing_ok=True)
                    item_dir.rmdir()
                    removed += 1
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Could not process storage dir %s during cleanup", item_dir)
        return removed
