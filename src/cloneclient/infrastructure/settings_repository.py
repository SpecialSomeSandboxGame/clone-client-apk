"""Persist user settings as JSON under the per-user data directory."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cloneclient.domain.settings import Settings
from cloneclient.infrastructure.paths import user_data_dir

logger = logging.getLogger("cloneclient.settings")


class SettingsRepository:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else user_data_dir() / "settings.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Settings:
        if not self._path.exists():
            return Settings()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Ignoring unreadable settings file at %s", self._path)
            return Settings()
        return Settings.from_dict(data)

    def save(self, settings: Settings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(settings.to_dict(), indent=2, sort_keys=True)
        self._path.write_text(payload + "\n", encoding="utf-8")
