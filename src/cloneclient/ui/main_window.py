"""Main application window."""

from __future__ import annotations

import logging

from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cloneclient.domain.settings import WindowGeometry
from cloneclient.services.diagnostics_service import collect_diagnostics
from cloneclient.services.inspect_service import InspectService
from cloneclient.services.repack_service import RepackService
from cloneclient.services.settings_service import SettingsService
from cloneclient.shared.constants import APP_NAME
from cloneclient.ui.repackager_view import RepackagerView
from cloneclient.ui.theme import stylesheet_for

logger = logging.getLogger("cloneclient.ui")


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings_service: SettingsService,
        inspect_service: InspectService | None = None,
        repack_service: RepackService | None = None,
    ) -> None:
        super().__init__()
        self._settings_service = settings_service
        self._settings = settings_service.load()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(640, 420)
        self.setStyleSheet(stylesheet_for(self._settings.theme))

        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        subtitle = QLabel("Repackage Android clients")
        subtitle.setObjectName("subtitle")
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(1 if self._settings.theme == "dark" else 0)
        self.theme_combo.blockSignals(False)
        self.theme_combo.currentIndexChanged.connect(self.change_theme)

        self.help_button = QPushButton("What changes?")
        self.help_button.setObjectName("ghost")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(QLabel("Theme"))
        header.addWidget(self.theme_combo)
        header.addSpacing(8)
        header.addWidget(self.help_button)

        self.repackager = RepackagerView(
            inspect_service or InspectService(),
            repack_service or RepackService(),
            settings_service,
        )
        self.help_button.clicked.connect(self.repackager.show_help)

        diagnostics = QWidget()
        diagnostics_layout = QVBoxLayout(diagnostics)
        diagnostics_layout.setContentsMargins(4, 4, 4, 4)
        diagnostics_layout.setSpacing(8)
        diagnostics_title = QLabel("Diagnostics")
        diagnostics_title.setObjectName("sectionTitle")
        diagnostics_subtitle = QLabel("Environment and runtime information")
        diagnostics_subtitle.setObjectName("muted")
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setPlainText(collect_diagnostics())
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("secondary")
        self.refresh_button.clicked.connect(self.refresh_report)
        self.copy_button = QPushButton("Copy diagnostics")
        self.copy_button.setObjectName("secondary")
        self.copy_button.clicked.connect(self.copy_report)
        diagnostics_buttons = QHBoxLayout()
        diagnostics_buttons.setContentsMargins(0, 0, 0, 0)
        diagnostics_buttons.addWidget(self.refresh_button)
        diagnostics_buttons.addWidget(self.copy_button)
        diagnostics_buttons.addStretch(1)
        diagnostics_layout.addWidget(diagnostics_title)
        diagnostics_layout.addWidget(diagnostics_subtitle)
        diagnostics_layout.addWidget(self.report, 1)
        diagnostics_layout.addLayout(diagnostics_buttons)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.repackager, "Repack")
        self.tabs.addTab(diagnostics, "Diagnostics")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(self.tabs, 1)

        container = QWidget()
        container.setObjectName("page")
        container.setLayout(layout)
        self.setCentralWidget(container)

        saved = self._settings.window_geometry
        if saved is not None:
            self.setGeometry(saved.x, saved.y, saved.width, saved.height)
        else:
            self.resize(1120, 780)

    def change_theme(self, index: int) -> None:
        theme = "dark" if index == 1 else "light"
        self.setStyleSheet(stylesheet_for(theme))
        try:
            self._settings_service.save_theme(theme)
        except OSError:
            logger.warning("Could not save theme", exc_info=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.repackager.is_busy():
            box = QMessageBox(self)
            box.setWindowTitle("Repack in progress")
            box.setText("A repack is still running. Cancel it and exit?")
            box.setInformativeText("The current repack will be stopped and partial files removed.")
            cancel_exit = box.addButton("Cancel and exit", QMessageBox.ButtonRole.DestructiveRole)
            keep_running = box.addButton("Keep running", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(keep_running)
            box.exec()
            if box.clickedButton() is not cancel_exit:
                event.ignore()
                return
            self.repackager.cancel_repack()
            self.repackager.shutdown()
        else:
            self.repackager.shutdown()
        rect = self.geometry()
        try:
            self._settings_service.save_window_geometry(
                WindowGeometry(rect.x(), rect.y(), rect.width(), rect.height())
            )
        except OSError:
            logger.warning("Could not save window geometry", exc_info=True)
        super().closeEvent(event)

    def refresh_report(self) -> None:
        self.report.setPlainText(collect_diagnostics())
        self.statusBar().showMessage("Diagnostics refreshed", 2000)

    def copy_report(self) -> None:
        QGuiApplication.clipboard().setText(self.report.toPlainText())
        self.statusBar().showMessage("Diagnostics copied to clipboard", 3000)
