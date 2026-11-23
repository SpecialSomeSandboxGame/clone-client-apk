"""Resolve per-user application paths on Windows."""

from __future__ import annotations

import os
from pathlib import Path

from cloneclient.shared.constants import APP_ID


def user_data_dir() -> Path:
    # LOCALAPPDATA is the Windows convention for per-user app data; APPDATA is
    # a fallback for shells that do not define it.
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    path = Path(base) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = user_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
