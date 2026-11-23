from pathlib import Path

from cloneclient.domain.settings import WindowGeometry
from cloneclient.infrastructure.settings_repository import SettingsRepository
from cloneclient.services.settings_service import SettingsService


def test_save_theme_preserves_geometry(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")
    service = SettingsService(repository)

    service.save_window_geometry(WindowGeometry(1, 2, 800, 600))
    service.save_theme("dark")

    settings = repository.load()
    assert settings.theme == "dark"
    assert settings.window_geometry is not None
    assert settings.window_geometry.width == 800


def test_save_geometry_preserves_theme(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")
    service = SettingsService(repository)

    service.save_theme("dark")
    service.save_window_geometry(WindowGeometry(1, 2, 800, 600))

    settings = repository.load()
    assert settings.theme == "dark"
    assert settings.window_geometry is not None


def test_save_repack_settings_preserves_other_values(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")
    service = SettingsService(repository)

    service.save_theme("dark")
    service.save_window_geometry(WindowGeometry(1, 2, 800, 600))
    service.save_repack_settings("D:/output", "D:/keys/release.jks", "release")

    settings = repository.load()
    assert settings.theme == "dark"
    assert settings.window_geometry is not None
    assert settings.repack_output_dir == "D:/output"
    assert settings.keystore_path == "D:/keys/release.jks"
    assert settings.keystore_alias == "release"
