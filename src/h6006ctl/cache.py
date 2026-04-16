"""Address cache for discovered H6006 bulbs."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path


def cache_path() -> Path:
    """Return path to the bulb cache file."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return base / "h6006ctl" / "bulbs.json"


def save_bulbs(bulbs: Sequence[dict[str, str]]) -> None:
    """Atomically write bulb list to cache. Warns to stderr on failure."""
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(list(bulbs), f, indent=2)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as exc:
        print(f"Warning: could not save bulb cache: {exc}", file=sys.stderr)


def load_bulbs() -> list[dict[str, str]] | None:
    """Load cached bulbs. Returns None on missing/corrupt/empty cache."""
    try:
        data = json.loads(cache_path().read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, list) or not data:
        return None
    for entry in data:
        if not isinstance(entry, dict) or "address" not in entry or "name" not in entry:
            return None
    return data
