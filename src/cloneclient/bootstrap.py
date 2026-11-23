"""Compose application dependencies and start the Qt event loop."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from cloneclient.domain.rename import build_rename_plan
from cloneclient.infrastructure.logging_setup import configure_logging, install_exception_hook
from cloneclient.infrastructure.paths import user_data_dir
from cloneclient.infrastructure.settings_repository import SettingsRepository
from cloneclient.infrastructure.toolchain import Toolchain
from cloneclient.services.inspect_service import InspectService
from cloneclient.services.repack_service import RepackService
from cloneclient.services.settings_service import SettingsService
from cloneclient.shared.constants import APP_ID, APP_NAME, NEW_PACKAGE, OLD_PACKAGE
from cloneclient.ui.main_window import MainWindow


def create_application(argv: list[str] | None = None) -> QApplication:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setFont(QFont("Segoe UI", 10))
    return app


def _stderr_notify(text: str) -> None:
    print(text, file=sys.stderr)


def _dialog_notify(text: str) -> None:
    QMessageBox.critical(None, "Unhandled error", text)


def _tool_check() -> int:
    try:
        import lief
        import PIL

        toolchain = Toolchain.discover()
        toolchain.require_java_17()
    except Exception as exc:
        print(f"tool check failed: {exc}", file=sys.stderr)
        return 1
    lines = [
        f"java: {toolchain.java} ({toolchain.java_version()})",
        f"lief: {lief.__version__}",
        f"pillow: {PIL.__version__}",
        f"apkeditor: {toolchain.apkeditor_jar}",
        f"apktool: {toolchain.apktool_jar}",
        f"signer: {toolchain.signer_jar}",
        f"keytool: {toolchain.keytool}",
    ]
    # A windowed PyInstaller build has no console, so persist the result for
    # headless verification of the bundled tool paths.
    try:
        report = user_data_dir() / "tool-check.txt"
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        lines.append(f"report: {report}")
    except OSError:
        pass
    print("\n".join(lines))
    return 0


def _inspect_file(path: Path) -> int:
    service = InspectService()
    try:
        info = service.inspect(path)
    except Exception as exc:
        print(f"inspection failed: {exc}", file=sys.stderr)
        return 1
    plan = None
    with contextlib.suppress(ValueError):
        plan = build_rename_plan(NEW_PACKAGE, old_package=info.package_name or OLD_PACKAGE)
    report = service.format_report(info, plan)
    try:
        report_path = user_data_dir() / "inspect-report.txt"
        report_path.write_text(report + "\n", encoding="utf-8")
    except OSError:
        pass
    print(report)
    return 0


def run(
    smoke: bool = False,
    crash_test: bool = False,
    tool_check: bool = False,
    inspect_path: Path | None = None,
) -> int:
    if tool_check:
        return _tool_check()
    if inspect_path is not None:
        return _inspect_file(inspect_path)
    logger = configure_logging()
    app = create_application()
    notify = _stderr_notify if (smoke or crash_test) else _dialog_notify
    install_exception_hook(logger, notify)
    if crash_test:
        try:
            raise RuntimeError("Crash handler self-test")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        return 1
    window = MainWindow(SettingsService(SettingsRepository()), InspectService(), RepackService())
    window.show()
    if smoke:
        app.processEvents()
        window.close()
        return 0
    return app.exec()
