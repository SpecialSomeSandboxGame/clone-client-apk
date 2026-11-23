from pathlib import Path

from cloneclient.domain.settings import Settings, WindowGeometry
from cloneclient.infrastructure.settings_repository import SettingsRepository


def test_repository_returns_defaults_when_file_is_missing(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")

    assert repository.load() == Settings()


def test_repository_round_trips_settings(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")
    settings = Settings(WindowGeometry(10, 20, 800, 600))

    repository.save(settings)

    assert repository.load() == settings


def test_repository_ignores_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    repository = SettingsRepository(path)

    assert repository.load() == Settings()
