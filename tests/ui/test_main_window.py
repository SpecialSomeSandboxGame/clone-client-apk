from pathlib import Path

from cloneclient.domain.settings import Settings
from cloneclient.infrastructure.settings_repository import SettingsRepository
from cloneclient.services.settings_service import SettingsService
from cloneclient.ui.main_window import MainWindow


def make_window(tmp_path: Path) -> MainWindow:
    service = SettingsService(SettingsRepository(tmp_path / "settings.json"))
    return MainWindow(service)


def test_main_window_shows_diagnostics(qtbot, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    qtbot.addWidget(window)

    assert window.windowTitle() == "CloneClient"
    assert "Application: CloneClient" in window.report.toPlainText()


def test_main_window_persists_geometry(qtbot, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    qtbot.addWidget(window)
    window.setGeometry(11, 22, 640, 420)

    window.show()
    window.close()

    saved = SettingsService(SettingsRepository(tmp_path / "settings.json")).load()
    assert saved.window_geometry is not None
    assert saved.window_geometry.width == 640


def test_main_window_persists_theme(qtbot, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    qtbot.addWidget(window)

    window.theme_combo.setCurrentIndex(1)

    saved = SettingsService(SettingsRepository(tmp_path / "settings.json")).load()
    assert saved.theme == "dark"
    assert window.styleSheet() != ""


def test_main_window_applies_saved_theme(qtbot, tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")
    repository.save(Settings(theme="dark"))
    window = MainWindow(SettingsService(repository))
    qtbot.addWidget(window)

    assert window.theme_combo.currentIndex() == 1
    assert window.styleSheet() != ""


def test_main_window_has_repackager_tab(qtbot, tmp_path: Path) -> None:
    window = make_window(tmp_path)
    qtbot.addWidget(window)

    assert window.tabs.count() == 2
    assert window.tabs.tabText(0) == "Repack"
    assert window.tabs.tabText(1) == "Diagnostics"
    assert window.repackager.package_edit.text() == "com.dev_rt.growtopia"
    assert window.repackager.keystore_edit.text()
