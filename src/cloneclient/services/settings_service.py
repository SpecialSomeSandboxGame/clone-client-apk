"""Coordinate settings loading and saving for the UI."""

from __future__ import annotations

from dataclasses import replace

from cloneclient.domain.settings import DEFAULT_THEME, THEMES, Settings, WindowGeometry
from cloneclient.infrastructure.settings_repository import SettingsRepository
from cloneclient.shared.constants import DEFAULT_KEYSTORE_ALIAS


class SettingsService:
    def __init__(self, repository: SettingsRepository) -> None:
        self._repository = repository

    def load(self) -> Settings:
        return self._repository.load()

    def save_window_geometry(self, geometry: WindowGeometry) -> None:
        current = self._repository.load()
        self._repository.save(replace(current, window_geometry=geometry))

    def save_theme(self, theme: str) -> None:
        current = self._repository.load()
        normalized = theme if theme in THEMES else DEFAULT_THEME
        self._repository.save(replace(current, theme=normalized))

    def save_repack_settings(self, output_dir: str, keystore_path: str, alias: str) -> None:
        current = self._repository.load()
        self._repository.save(
            replace(
                current,
                repack_output_dir=output_dir.strip() or None,
                keystore_path=keystore_path.strip() or None,
                keystore_alias=alias.strip() or DEFAULT_KEYSTORE_ALIAS,
            )
        )
