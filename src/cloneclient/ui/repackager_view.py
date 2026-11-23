"""Repack workflow with explicit state, validation, and cancellation."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cloneclient.domain.apk import ApkInfo
from cloneclient.domain.rename import build_rename_plan
from cloneclient.domain.server import SERVER_1, SERVER_2, validate_server
from cloneclient.infrastructure.appearance import validate_app_name, validate_icon
from cloneclient.infrastructure.keystore import default_keystore_path
from cloneclient.services.inspect_service import InspectService
from cloneclient.services.repack_service import RepackRequest, RepackResult, RepackService
from cloneclient.services.settings_service import SettingsService
from cloneclient.shared.constants import (
    DEFAULT_KEYSTORE_ALIAS,
    KEY_PASSWORD_MIN_MESSAGE,
    MIN_KEY_PASSWORD_LENGTH,
    NEW_PACKAGE,
    OLD_PACKAGE,
)
from cloneclient.shared.errors import InputError
from cloneclient.ui.worker import FunctionWorker, LogLine, Progress

logger = logging.getLogger("cloneclient.ui.repackager")

STAGES = (
    "Merge",
    "Decode",
    "Rename",
    "Appearance",
    "Rebuild",
    "Sign",
    "Verify",
)


def _label(text: str, object_name: str = "", word_wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(word_wrap)
    return label


def _muted(text: str, word_wrap: bool = False) -> QLabel:
    return _label(text, "muted", word_wrap)


def _field_label(text: str) -> QLabel:
    return _label(text, "fieldLabel")


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(8)
    layout.addWidget(_label(title, "sectionTitle"))
    return card, layout


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


class RepackagerView(QWidget):
    def __init__(
        self,
        inspect_service: InspectService,
        repack_service: RepackService,
        settings_service: SettingsService | None = None,
        check_tools_on_start: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._inspect_service = inspect_service
        self._repack_service = repack_service
        self._settings_service = settings_service
        self._worker: FunctionWorker | None = None
        self._tools_worker: FunctionWorker | None = None
        self._info: ApkInfo | None = None
        self._result: RepackResult | None = None
        self._busy = False
        self._cancel_event: threading.Event | None = None
        self._sticky_status: str = ""
        self._outcome: str = ""
        self._tools_ready = False
        self._tools_checked = False
        self._tools_message = "Java and tools have not been checked yet."
        self._keystore_ok = True
        self._left_scroll: QScrollArea | None = None
        self._right_scroll: QScrollArea | None = None
        self._tools_timer: QTimer | None = None
        self._build_ui()
        self._load_settings()
        self._connect()
        self._install_shortcuts()
        self._set_busy(False)
        self._validate_form()
        self.input_edit.setFocus()
        if check_tools_on_start:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self.check_tools)
            timer.start(250)
            self._tools_timer = timer

    # ------------------------------------------------------------------ setup
    def _build_ui(self) -> None:
        self.setAcceptDrops(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 12)
        outer.setSpacing(12)

        footer = QFrame()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)
        footer_layout.setSpacing(10)
        # One status line for the whole screen. Duplicating progress messages in
        # the footer, the progress card, and the result card made failures read
        # as three separate problems.
        self.status = _muted("Select a source package to begin.", True)
        footer_layout.addWidget(self.status, 1)
        # Details live in the footer so the log and package report stay reachable
        # in every state, including an inspection that failed before any run.
        self.details_toggle = QToolButton()
        self.details_toggle.setObjectName("link")
        self.details_toggle.setText("Show details")
        self.details_toggle.setCheckable(True)
        footer_layout.addWidget(self.details_toggle)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.hide()
        footer_layout.addWidget(self.cancel_button)
        self.repack_button = QPushButton("Repack APK")
        self.repack_button.setObjectName("primary")
        self.repack_button.setMinimumWidth(160)
        footer_layout.addWidget(self.repack_button)

        # One page scroll instead of two independent scroll areas: with two,
        # the right column could clip its progress card while the left column
        # scrolled separately, which read as two unrelated panes.
        page = QWidget()
        page.setObjectName("scrollContent")
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(16)
        page_layout.addWidget(self._build_left(), 3)
        page_layout.addWidget(self._build_right(), 2)
        self._page_scroll = self._scroll(page)
        self._left_scroll = self._page_scroll
        self._right_scroll = self._page_scroll
        outer.addWidget(self._page_scroll, 1)
        outer.addWidget(footer)

    def _build_left(self) -> QWidget:
        content = QWidget()
        content.setObjectName("scrollContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        source_card, source_layout = _card("Source package")
        self.file_info = _muted("Drop an XAPK or APK here, or choose a file.", True)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Path to an .xapk or .apk file")
        self.input_button = QPushButton("Choose...")
        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(8)
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.input_button)
        self.inspect_button = QPushButton("Refresh info")
        self.inspect_button.setObjectName("ghost")
        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(8)
        info_row.addWidget(self.file_info, 1)
        info_row.addWidget(self.inspect_button)
        source_layout.addLayout(info_row)
        source_layout.addLayout(input_row)
        layout.addWidget(source_card)

        identity_card, identity_layout = _card("App identity")
        current_row = QHBoxLayout()
        current_row.setContentsMargins(0, 0, 0, 0)
        current_row.setSpacing(8)
        current_row.addWidget(_field_label("Current package"))
        self.old_package_label = _label("Not inspected yet", "mono", True)
        self.old_package_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        current_row.addWidget(self.old_package_label, 1)
        identity_layout.addLayout(current_row)
        identity_layout.addWidget(_field_label("New application id"))
        self.package_edit = QLineEdit(NEW_PACKAGE)
        self.package_edit.setPlaceholderText("com.example.client")
        identity_layout.addWidget(self.package_edit)
        self.package_error = _label("", "error", True)
        self.package_error.hide()
        identity_layout.addWidget(self.package_error)
        self.package_help = _muted(
            "Letters, digits, and underscores only. Hyphens are invalid. "
            f"The id must be exactly {len(OLD_PACKAGE)} characters.",
            True,
        )
        identity_layout.addWidget(self.package_help)
        layout.addWidget(identity_card)

        appearance_card, appearance_layout = _card("Appearance")
        appearance_layout.addWidget(_field_label("App name"))
        self.app_name_edit = QLineEdit()
        self.app_name_edit.setPlaceholderText("Keep the current app name")
        appearance_layout.addWidget(self.app_name_edit)
        self.app_name_error = _label("", "error", True)
        self.app_name_error.hide()
        appearance_layout.addWidget(self.app_name_error)
        appearance_layout.addWidget(
            _muted(
                "Shown under the launcher icon. Leave empty to keep the current name.",
                True,
            )
        )

        appearance_layout.addWidget(_field_label("App icon"))
        self.icon_edit = QLineEdit()
        self.icon_edit.setPlaceholderText("Keep the current icon")
        self.icon_button = QPushButton("Choose...")
        self.icon_clear = QToolButton()
        self.icon_clear.setObjectName("link")
        self.icon_clear.setText("Clear")
        self.icon_clear.hide()
        icon_row = QHBoxLayout()
        icon_row.setContentsMargins(0, 0, 0, 0)
        icon_row.setSpacing(8)
        icon_row.addWidget(self.icon_edit, 1)
        icon_row.addWidget(self.icon_button)
        icon_row.addWidget(self.icon_clear)
        appearance_layout.addLayout(icon_row)
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_preview.hide()
        appearance_layout.addWidget(self.icon_preview)
        self.icon_error = _label("", "error", True)
        self.icon_error.hide()
        appearance_layout.addWidget(self.icon_error)
        appearance_layout.addWidget(
            _muted(
                "PNG, JPG, or WebP. Minimum 48x48. Non-square images are center-cropped.",
                True,
            )
        )
        layout.addWidget(appearance_card)

        server_card, server_layout = _card("Server endpoints")
        server_layout.addWidget(
            _muted(
                "Optional. Replace the Growtopia hosts inside libgrowtopia.so. "
                f"Each value must be exactly {len(SERVER_1)} characters.",
                True,
            )
        )
        server_layout.addWidget(_field_label("Server 1"))
        self.server1_edit = QLineEdit()
        self.server1_edit.setPlaceholderText(SERVER_1)
        self.server1_edit.setMaxLength(len(SERVER_1))
        server_layout.addWidget(self.server1_edit)
        self.server1_error = _label("", "error", True)
        self.server1_error.hide()
        server_layout.addWidget(self.server1_error)
        server_layout.addWidget(_field_label("Server 2"))
        self.server2_edit = QLineEdit()
        self.server2_edit.setPlaceholderText(SERVER_2)
        self.server2_edit.setMaxLength(len(SERVER_2))
        server_layout.addWidget(self.server2_edit)
        self.server2_error = _label("", "error", True)
        self.server2_error.hide()
        server_layout.addWidget(self.server2_error)
        layout.addWidget(server_card)

        destination_card, destination_layout = _card("Output and signing")
        destination_layout.addWidget(_field_label("Output folder"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Defaults to a folder next to the input file")
        self.output_button = QPushButton("Choose...")
        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(8)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)
        destination_layout.addLayout(output_row)
        self.output_error = _label("", "error", True)
        self.output_error.hide()
        destination_layout.addWidget(self.output_error)

        destination_layout.addWidget(_field_label("Keystore password"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText(f"At least {MIN_KEY_PASSWORD_LENGTH} characters")
        self.password_toggle = QToolButton()
        self.password_toggle.setText("Show")
        self.password_toggle.setCheckable(True)
        password_row = QHBoxLayout()
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.setSpacing(8)
        password_row.addWidget(self.password_edit, 1)
        password_row.addWidget(self.password_toggle)
        destination_layout.addLayout(password_row)
        self.password_error = _label("", "error", True)
        self.password_error.hide()
        destination_layout.addWidget(self.password_error)
        destination_layout.addWidget(
            _muted(
                "Used for this session only. Minimum "
                f"{MIN_KEY_PASSWORD_LENGTH} characters. "
                "Keep one keystore for all releases.",
                True,
            )
        )

        destination_layout.addWidget(_field_label("Release keystore"))
        self.keystore_edit = QLineEdit(str(default_keystore_path()))
        self.keystore_button = QPushButton("Choose...")
        keystore_row = QHBoxLayout()
        keystore_row.setContentsMargins(0, 0, 0, 0)
        keystore_row.setSpacing(8)
        keystore_row.addWidget(self.keystore_edit, 1)
        keystore_row.addWidget(self.keystore_button)
        destination_layout.addLayout(keystore_row)
        self.keystore_status = _muted("", True)
        destination_layout.addWidget(self.keystore_status)

        self.advanced_button = QToolButton()
        self.advanced_button.setText("Advanced")
        self.advanced_button.setCheckable(True)
        self.advanced_button.setArrowType(Qt.ArrowType.RightArrow)
        destination_layout.addWidget(self.advanced_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.alias_container = QWidget()
        alias_layout = QVBoxLayout(self.alias_container)
        alias_layout.setContentsMargins(0, 0, 0, 0)
        alias_layout.setSpacing(4)
        alias_layout.addWidget(_field_label("Keystore alias"))
        self.alias_edit = QLineEdit(DEFAULT_KEYSTORE_ALIAS)
        alias_layout.addWidget(self.alias_edit)
        alias_layout.addWidget(
            _muted("Only change this when your keystore uses another alias.", True)
        )
        self.alias_container.hide()
        destination_layout.addWidget(self.alias_container)
        layout.addWidget(destination_card)
        layout.addStretch(1)

        return content

    def _build_right(self) -> QWidget:
        content = QWidget()
        content.setObjectName("scrollContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        summary_card, summary_layout = _card("Package details")
        self.summary_placeholder = _muted(
            "Choose an XAPK or APK to start.\n\n"
            "1. Select the source package.\n"
            "2. Review the new application id and the warnings.\n"
            "3. Repack and sign the APK.",
            True,
        )
        summary_layout.addWidget(self.summary_placeholder)
        self.summary_content = QWidget()
        summary_grid = QGridLayout(self.summary_content)
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(12)
        summary_grid.setVerticalSpacing(2)
        self.summary_values: dict[str, QLabel] = {}
        keys = ("Version", "SDK", "ABIs", "Densities", "Languages", "OBB")
        for row, key in enumerate(keys):
            key_label = _muted(key)
            value = _label("-", "", True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            summary_grid.addWidget(key_label, row, 0)
            summary_grid.addWidget(value, row, 1)
            self.summary_values[key] = value
        summary_grid.setColumnStretch(1, 1)
        self.summary_content.hide()
        summary_layout.addWidget(self.summary_content)
        self.warnings_label = _label("", "warning", True)
        self.warnings_label.hide()
        summary_layout.addWidget(self.warnings_label)
        layout.addWidget(summary_card)

        # Only unmet requirements appear here. A checklist that always lists six
        # green "Ready" rows costs reading time and hides the one item that
        # actually needs attention.
        self.blockers_card, blockers_layout = _card("Needs attention")
        self.blockers_card.hide()
        self.blockers_list = QVBoxLayout()
        self.blockers_list.setContentsMargins(0, 0, 0, 0)
        self.blockers_list.setSpacing(2)
        blockers_layout.addLayout(self.blockers_list)
        self.blocker_labels: dict[str, QLabel] = {}
        for key in (
            "Source",
            "Application id",
            "App name",
            "App icon",
            "Server 1",
            "Server 2",
            "Output folder",
            "Keystore",
            "Password",
        ):
            label = _label("", "stageFailed", True)
            label.hide()
            self.blockers_list.addWidget(label)
            self.blocker_labels[key] = label
        self.tools_detail = _label("", "error", True)
        self.tools_detail.hide()
        blockers_layout.addWidget(self.tools_detail)
        self.tools_button = QPushButton("Check tools")
        self.tools_button.setObjectName("ghost")
        blockers_layout.addWidget(self.tools_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.blockers_card)

        progress_card, progress_layout = _card("Progress")
        # Reserved space would push the result out of view before anything runs.
        self.progress_card = progress_card
        progress_card.hide()
        progress_layout.setSpacing(4)
        self.stage_status: dict[str, QLabel] = {}
        for name in STAGES:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(_muted(name), 1)
            status = _label("Pending", "stagePending")
            row.addWidget(status)
            progress_layout.addLayout(row)
            self.stage_status[name] = status
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        progress_layout.addWidget(self.progress)
        layout.addWidget(progress_card)

        self.result_card = QFrame()
        self.result_card.setObjectName("resultCard")
        self.result_card.hide()
        result_layout = QVBoxLayout(self.result_card)
        result_layout.setContentsMargins(16, 14, 16, 16)
        result_layout.setSpacing(8)
        self.result_title = _label("", "resultNeutral")
        result_layout.addWidget(self.result_title)
        self.result_detail = _label("", "", True)
        self.result_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result_layout.addWidget(self.result_detail)
        result_buttons = QHBoxLayout()
        result_buttons.setContentsMargins(0, 0, 0, 0)
        result_buttons.setSpacing(8)
        self.open_output_button = QPushButton("Open folder")
        self.open_output_button.setObjectName("secondary")
        self.open_output_button.hide()
        self.copy_output_button = QPushButton("Copy path")
        self.copy_output_button.setObjectName("ghost")
        self.copy_output_button.hide()
        result_buttons.addWidget(self.open_output_button)
        result_buttons.addWidget(self.copy_output_button)
        result_buttons.addStretch(1)
        result_layout.addLayout(result_buttons)
        layout.addWidget(self.result_card)

        self.details_panel = QFrame()
        self.details_panel.setObjectName("card")
        self.details_panel.hide()
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(16, 14, 16, 16)
        details_layout.setSpacing(8)
        details_header = QHBoxLayout()
        details_header.setContentsMargins(0, 0, 0, 0)
        details_header.addWidget(_label("Details", "sectionTitle"), 1)
        self.copy_details_button = QPushButton("Copy current tab")
        self.copy_details_button.setObjectName("ghost")
        details_header.addWidget(self.copy_details_button)
        details_layout.addLayout(details_header)
        self.details_tabs = QTabWidget()
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setPlainText("Select a package to see its details.")
        self.diagnostics.setMinimumHeight(200)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setMinimumHeight(200)
        self.details_tabs.addTab(self.diagnostics, "Package")
        self.details_tabs.addTab(self.log, "Log")
        details_layout.addWidget(self.details_tabs)
        self.details_hint = _muted("")
        details_layout.addWidget(self.details_hint)
        layout.addWidget(self.details_panel)
        layout.addStretch(1)

        return content

    @staticmethod
    def _scroll(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumSize(0, 0)
        scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        scroll.setWidget(content)
        return scroll

    def _connect(self) -> None:
        self.input_button.clicked.connect(self.browse_input)
        self.output_button.clicked.connect(self.browse_output)
        self.keystore_button.clicked.connect(self.browse_keystore)
        self.inspect_button.clicked.connect(self.inspect_input)
        self.repack_button.clicked.connect(self.repack)
        self.cancel_button.clicked.connect(self.cancel_repack)
        self.input_edit.textChanged.connect(self._on_input_changed)
        self.input_edit.editingFinished.connect(self._maybe_inspect_typed)
        self.package_edit.textChanged.connect(self._user_edited)
        self.app_name_edit.textChanged.connect(self._user_edited)
        self.icon_edit.textChanged.connect(self._on_icon_changed)
        self.icon_button.clicked.connect(self.browse_icon)
        self.icon_clear.clicked.connect(self.clear_icon)
        self.server1_edit.textChanged.connect(self._user_edited)
        self.server2_edit.textChanged.connect(self._user_edited)
        self.output_edit.textChanged.connect(self._user_edited)
        self.keystore_edit.textChanged.connect(self._on_keystore_changed)
        self.password_edit.textChanged.connect(self._user_edited)
        self.password_toggle.toggled.connect(self._toggle_password)
        self.advanced_button.toggled.connect(self._toggle_advanced)
        self.details_toggle.toggled.connect(self._toggle_details)
        self.copy_details_button.clicked.connect(self._copy_details)
        self.tools_button.clicked.connect(self.check_tools)
        self.open_output_button.clicked.connect(self._open_output)
        self.copy_output_button.clicked.connect(self._copy_output)

    def _install_shortcuts(self) -> None:
        # Keyboard access keeps the workflow usable without reaching for the mouse.
        self._shortcuts: list[QShortcut] = []
        for keys, slot in (
            ("Ctrl+O", self.browse_input),
            ("Ctrl+R", self.repack),
            ("Esc", self.cancel_repack),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(slot)
            self._shortcuts.append(shortcut)
        self.input_button.setToolTip("Choose a source package (Ctrl+O)")
        self.repack_button.setToolTip("Repack and sign the APK (Ctrl+R)")
        self.cancel_button.setToolTip("Cancel the running repack (Esc)")

    def _load_settings(self) -> None:
        if self._settings_service is None:
            self._update_keystore_status()
            return
        settings = self._settings_service.load()
        if settings.repack_output_dir:
            self.output_edit.setText(settings.repack_output_dir)
        if settings.keystore_path:
            self.keystore_edit.setText(settings.keystore_path)
        if settings.keystore_alias:
            self.alias_edit.setText(settings.keystore_alias)
        self._update_keystore_status()

    # --------------------------------------------------------------- selection
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                suffix = Path(url.toLocalFile()).suffix.lower()
                if suffix in {".xapk", ".apk"}:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in {".xapk", ".apk"}:
                self._select_input(path)
                event.acceptProposedAction()
                return
        event.ignore()

    def browse_input(self) -> None:
        start = str(Path.home())
        if self.input_edit.text().strip():
            start = str(Path(self.input_edit.text().strip()).parent)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Android package",
            start,
            "Android packages (*.xapk *.apk);;All files (*)",
        )
        if path:
            self._select_input(Path(path))

    def _select_input(self, path: Path) -> None:
        self._info = None
        self._result = None
        self.summary_content.hide()
        self.summary_placeholder.show()
        self.warnings_label.hide()
        self.result_card.hide()
        self._reset_stages()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.input_edit.setText(str(path))
        self.file_info.setText("Selected. Reading package information...")
        if not self.output_edit.text().strip():
            self.output_edit.setText(str(path.parent / "output"))
        self.inspect_input()

    def _on_input_changed(self) -> None:
        if self._info is not None:
            text = self.input_edit.text().strip()
            if not text or Path(text) != self._info.source:
                self._info = None
                self.summary_content.hide()
                self.summary_placeholder.show()
                self.warnings_label.hide()
                self.result_card.hide()
                self._reset_stages()
                self.progress.setRange(0, 100)
                self.progress.setValue(0)
                self.diagnostics.setPlainText("Select a package to see its details.")
                self.status.setText("Waiting for a package.")
        self._validate_form()

    def _maybe_inspect_typed(self) -> None:
        if self._busy:
            return
        text = self.input_edit.text().strip()
        if not text:
            return
        path = Path(text)
        if path.suffix.lower() not in {".xapk", ".apk"} or not path.exists():
            return
        if self._info is not None and self._info.source == path:
            return
        self._select_input(path)

    def _input_path(self) -> Path | None:
        text = self.input_edit.text().strip()
        if not text:
            self._set_footer_error("Select an XAPK or APK first.")
            return None
        path = Path(text)
        if not path.exists():
            self._set_footer_error("Input file does not exist.")
            return None
        if path.suffix.lower() not in {".xapk", ".apk"}:
            self._set_footer_error("Select an .xapk or .apk file.")
            return None
        return path

    def _set_footer_error(self, message: str) -> None:
        self._sticky_status = ""
        self.status.setText(message)

    def _user_edited(self) -> None:
        # Editing a field means the user has moved past the last outcome, so
        # the sticky message should stop masking the new validation reason.
        self._sticky_status = ""
        self._validate_form()

    def inspect_input(self) -> None:
        if self._busy:
            return
        source = self._input_path()
        if source is None:
            return
        self._result = None
        self.result_card.hide()
        self.summary_content.hide()
        self.summary_placeholder.show()
        self.warnings_label.hide()
        self._reset_stages()
        self.progress.setRange(0, 0)
        self.progress.setValue(0)
        self.status.setText("Reading package information...")
        self.diagnostics.setPlainText("Inspecting package...")
        self.log.clear()
        self._set_busy(True, cancellable=False)
        self.inspect_button.setText("Inspecting...")
        self._start_worker(
            lambda progress, log: self._inspect(source, progress, log),
            self._on_inspected,
            self._on_inspect_failed,
        )

    def _inspect(
        self,
        source: Path,
        progress: Progress,
        log: LogLine,
    ) -> tuple[ApkInfo, str]:
        info = self._inspect_service.inspect(source, log)
        plan = self._plan_or_none(info)
        return info, self._inspect_service.format_report(info, plan)

    def _on_inspected(self, result: object) -> None:
        info, report = result  # type: ignore[misc]
        if not isinstance(info, ApkInfo):
            return
        self._info = info
        self._apply_info(info, report)
        self._set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._reset_stages()
        self.status.setText("Review the summary, then repack.")
        self._save_settings()
        self._validate_form()

    def _apply_info(self, info: ApkInfo, report: str) -> None:
        self.file_info.setText(
            f"{_format_size(info.total_size)} - "
            f"{'XAPK' if info.is_xapk else 'APK'} - {info.split_count} package(s)"
        )
        old_package = info.package_name or OLD_PACKAGE
        self.old_package_label.setText(info.package_name or "unknown")
        self.package_help.setText(
            "Letters, digits, and underscores only. Hyphens are invalid. "
            f"The id must be exactly {len(old_package)} characters."
        )
        self.summary_values["Version"].setText(
            f"{info.version_name or 'unknown'} ({info.version_code or 'unknown'})"
        )
        self.summary_values["SDK"].setText(
            f"min {info.min_sdk if info.min_sdk is not None else '?'} / "
            f"target {info.target_sdk if info.target_sdk is not None else '?'}"
        )
        self.summary_values["ABIs"].setText(", ".join(info.abis) or "none")
        self.summary_values["Densities"].setText(", ".join(info.densities) or "none")
        self.summary_values["Languages"].setText(", ".join(info.languages) or "none")
        self.summary_values["OBB"].setText("yes" if info.has_obb else "no")
        self.summary_placeholder.hide()
        self.summary_content.show()
        plan = self._plan_or_none(info)
        warnings = self._inspect_service.warnings(info, plan)
        self.warnings_label.setText("\n".join(warnings))
        self.warnings_label.setVisible(bool(warnings))
        self.diagnostics.setPlainText(report)

    def _plan_or_none(self, info: ApkInfo):
        try:
            return build_rename_plan(
                self.package_edit.text().strip(),
                old_package=info.package_name or OLD_PACKAGE,
            )
        except ValueError:
            return None

    def _on_inspect_failed(self, message: str) -> None:
        self._set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._reset_stages()
        self.status.setText("Inspection failed. Choose another file or try again.")
        self._append_log(f"ERROR: {message}")
        self._show_result("error", "Inspection failed", message.splitlines()[0])

    # --------------------------------------------------------------- validation
    def _validate_form(self) -> None:
        if self._busy:
            self.repack_button.setEnabled(False)
            return
        input_ok = self._input_valid()
        self.inspect_button.setEnabled(input_ok)
        info_ok = self._info is not None
        package_ok = self._validate_package()
        name_ok, icon_ok = self._validate_appearance()
        server1_ok, server2_ok = self._validate_servers()
        output_ok = self._validate_output()
        keystore_ok = self._validate_keystore()
        password_ok, password_message = self._validate_password()
        # A background tool check must not block the primary action. The
        # repack worker discovers the same toolchain and reports a clear error
        # if Java is missing, so pending state stays non-blocking.
        tools_ok = self._tools_ready or not self._tools_checked
        all_ok = (
            input_ok
            and info_ok
            and package_ok
            and name_ok
            and icon_ok
            and server1_ok
            and server2_ok
            and output_ok
            and keystore_ok
            and password_ok
            and tools_ok
        )
        # Source stays quiet until the user has started a run. Flagging an empty
        # form as needing attention on launch reads as an error state.
        self._update_preflight(
            {
                "Source": input_ok or not self.input_edit.text().strip(),
                "Application id": package_ok or not self.package_edit.hasFocus(),
                "App name": name_ok or not self.app_name_edit.text().strip(),
                "App icon": icon_ok or not self.icon_edit.text().strip(),
                "Server 1": server1_ok or not self.server1_edit.text().strip(),
                "Server 2": server2_ok or not self.server2_edit.text().strip(),
                "Output folder": output_ok,
                "Keystore": keystore_ok,
                "Password": password_ok,
            }
        )
        self.repack_button.setEnabled(all_ok)
        if not input_ok:
            reason = "Select an XAPK or APK."
        elif not info_ok:
            reason = "Inspect the selected package."
        elif not package_ok:
            reason = "Fix the application id."
        elif not name_ok:
            reason = "Fix the app name."
        elif not icon_ok:
            reason = "Choose a valid app icon."
        elif not server1_ok:
            reason = "Fix the Server 1 endpoint."
        elif not server2_ok:
            reason = "Fix the Server 2 endpoint."
        elif not output_ok:
            reason = "Choose a valid output folder."
        elif not keystore_ok:
            reason = "Choose a valid keystore path."
        elif not password_ok:
            reason = password_message
        elif not tools_ok:
            reason = self._tools_message
        elif not self._tools_checked:
            reason = "Ready to repack. Checking Java in the background."
        else:
            reason = "Ready to repack."
        # An outcome message outlives the revalidation that follows a worker
        # exit, so the user can still read what happened.
        self.status.setText(self._sticky_status or reason)

    def _input_valid(self) -> bool:
        text = self.input_edit.text().strip()
        if not text:
            return False
        path = Path(text)
        return path.is_file() and path.suffix.lower() in {".xapk", ".apk"}

    def _validate_package(self) -> bool:
        text = self.package_edit.text().strip()
        if not text:
            self.package_error.setText("Enter an application id.")
            self.package_error.show()
            self.package_edit.setProperty("invalid", True)
            _repolish(self.package_edit)
            return False
        old_package = self._info.package_name if self._info else OLD_PACKAGE
        try:
            build_rename_plan(text, old_package=old_package or OLD_PACKAGE)
        except ValueError as exc:
            self.package_error.setText(str(exc))
            self.package_error.show()
            self.package_edit.setProperty("invalid", True)
            _repolish(self.package_edit)
            return False
        self.package_error.hide()
        self.package_edit.setProperty("invalid", False)
        _repolish(self.package_edit)
        return True

    def _validate_appearance(self) -> tuple[bool, bool]:
        name = self.app_name_edit.text().strip()
        name_ok = True
        if name:
            try:
                validate_app_name(name)
            except InputError as exc:
                self.app_name_error.setText(str(exc))
                self.app_name_error.show()
                self.app_name_edit.setProperty("invalid", True)
                _repolish(self.app_name_edit)
                name_ok = False
            else:
                self.app_name_error.hide()
                self.app_name_edit.setProperty("invalid", False)
                _repolish(self.app_name_edit)
        else:
            self.app_name_error.hide()
            self.app_name_edit.setProperty("invalid", False)
            _repolish(self.app_name_edit)

        icon_text = self.icon_edit.text().strip()
        icon_ok = True
        if icon_text:
            try:
                validate_icon(Path(icon_text))
            except InputError as exc:
                self.icon_error.setText(str(exc))
                self.icon_error.show()
                self.icon_edit.setProperty("invalid", True)
                _repolish(self.icon_edit)
                self._update_icon_preview(None)
                icon_ok = False
            else:
                self.icon_error.hide()
                self.icon_edit.setProperty("invalid", False)
                _repolish(self.icon_edit)
                self._update_icon_preview(Path(icon_text))
        else:
            self.icon_error.hide()
            self.icon_edit.setProperty("invalid", False)
            _repolish(self.icon_edit)
            self._update_icon_preview(None)
        self.icon_clear.setVisible(bool(icon_text))
        return name_ok, icon_ok

    def _validate_servers(self) -> tuple[bool, bool]:
        first = self._validate_server_field(self.server1_edit, self.server1_error, "Server 1")
        second = self._validate_server_field(self.server2_edit, self.server2_error, "Server 2")
        return first, second

    def _validate_server_field(
        self,
        field: QLineEdit,
        error: QLabel,
        label: str,
    ) -> bool:
        value = field.text().strip()
        if not value:
            error.hide()
            field.setProperty("invalid", False)
            _repolish(field)
            return True
        try:
            validate_server(value, label)
        except ValueError as exc:
            error.setText(str(exc))
            error.show()
            field.setProperty("invalid", True)
            _repolish(field)
            return False
        error.hide()
        field.setProperty("invalid", False)
        _repolish(field)
        return True

    def _update_icon_preview(self, path: Path | None) -> None:
        if path is None:
            self.icon_preview.clear()
            self.icon_preview.hide()
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.icon_preview.clear()
            self.icon_preview.hide()
            return
        self.icon_preview.setPixmap(
            pixmap.scaled(
                64,
                64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.icon_preview.show()

    def _validate_output(self) -> bool:
        text = self.output_edit.text().strip()
        if text and Path(text).is_file():
            self.output_error.setText("Choose a folder, not a file.")
            self.output_error.show()
            return False
        self.output_error.hide()
        return True

    def _validate_keystore(self) -> bool:
        text = self.keystore_edit.text().strip()
        if text and Path(text).is_dir():
            self._keystore_ok = False
            return False
        self._keystore_ok = True
        return True

    def _validate_password(self) -> tuple[bool, str]:
        password = self.password_edit.text()
        if not password:
            self.password_error.hide()
            self.password_edit.setProperty("invalid", False)
            _repolish(self.password_edit)
            return False, "Enter the keystore password."
        if len(password) < MIN_KEY_PASSWORD_LENGTH:
            self.password_error.setText(KEY_PASSWORD_MIN_MESSAGE)
            self.password_error.show()
            self.password_edit.setProperty("invalid", True)
            _repolish(self.password_edit)
            return False, KEY_PASSWORD_MIN_MESSAGE
        self.password_error.hide()
        self.password_edit.setProperty("invalid", False)
        _repolish(self.password_edit)
        return True, ""

    def _update_preflight(self, checks: dict[str, bool]) -> None:
        hints = {
            "Source": "Choose an XAPK or APK file.",
            "Application id": "Fix the application id to a valid name.",
            "App name": "Fix the app name.",
            "App icon": "Choose a valid app icon.",
            "Server 1": "Fix the Server 1 endpoint.",
            "Server 2": "Fix the Server 2 endpoint.",
            "Output folder": "Choose a writable output folder.",
            "Keystore": "Choose a keystore file, not a folder.",
            "Password": "Enter the keystore password.",
        }
        if self.package_error.text() and not self.package_error.isHidden():
            hints["Application id"] = self.package_error.text()
        password = self.password_edit.text()
        if password and len(password) < MIN_KEY_PASSWORD_LENGTH:
            hints["Password"] = KEY_PASSWORD_MIN_MESSAGE
        visible = False
        for key, label in self.blocker_labels.items():
            ok = checks.get(key, False)
            hint = hints[key]
            label.setVisible(not ok)
            if not ok:
                label.setText(hint)
                visible = True
        tools_failed = self._tools_checked and not self._tools_ready
        self.blockers_card.setVisible(visible or tools_failed)

    # --------------------------------------------------------------- signing
    def browse_output(self) -> None:
        start = self.output_edit.text().strip()
        if not start:
            start = str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "Select output folder", start)
        if path:
            self.output_edit.setText(path)

    def browse_icon(self) -> None:
        start = self.icon_edit.text().strip()
        if not start:
            start = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select app icon",
            start,
            "Images (*.png *.jpg *.jpeg *.webp);;All files (*)",
        )
        if path:
            self.icon_edit.setText(path)

    def clear_icon(self) -> None:
        self.icon_edit.clear()

    def _on_icon_changed(self) -> None:
        self._user_edited()

    def browse_keystore(self) -> None:
        start = self.keystore_edit.text().strip() or str(default_keystore_path())
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select release keystore",
            start,
            "Keystore (*.jks *.keystore);;All files (*)",
        )
        if path:
            self.keystore_edit.setText(path)

    def _on_keystore_changed(self) -> None:
        self._update_keystore_status()
        self._user_edited()

    def _update_keystore_status(self) -> None:
        text = self.keystore_edit.text().strip()
        if not text:
            self.keystore_status.setText(
                "The default release keystore will be created on the first repack."
            )
        elif Path(text).exists() and Path(text).is_dir():
            self.keystore_status.setText("Choose a keystore file, not a folder.")
        elif Path(text).exists():
            self.keystore_status.setText(
                "Existing keystore. Keep it for every release so updates install."
            )
        else:
            self.keystore_status.setText("A new keystore will be created on the first repack.")
        self.keystore_status.setObjectName(
            "error" if "not a folder" in self.keystore_status.text() else "muted"
        )
        _repolish(self.keystore_status)

    def _toggle_password(self, checked: bool) -> None:
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.password_toggle.setText("Hide" if checked else "Show")

    def _toggle_advanced(self, checked: bool) -> None:
        self.alias_container.setVisible(checked)
        self.advanced_button.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    # ------------------------------------------------------------------ tools
    def check_tools(self) -> None:
        if self._tools_worker is not None and self._tools_worker.isRunning():
            return
        self._tools_checked = False
        self._tools_ready = False
        self._tools_message = "Checking Java and tools..."
        self.tools_detail.hide()
        self.tools_button.setEnabled(False)
        self.tools_button.setText("Checking...")
        self._validate_form()
        worker = FunctionWorker(lambda progress, log: self._repack_service.check_tools(), self)
        worker.succeeded.connect(self._on_tools_ready)
        worker.failed.connect(self._on_tools_failed)
        worker.finished.connect(self._on_tools_finished)
        self._tools_worker = worker
        worker.start()

    def _on_tools_ready(self, message: object) -> None:
        self._tools_checked = True
        self._tools_ready = True
        self._tools_message = str(message)
        self.tools_detail.hide()
        self.tools_button.setText("Check tools")
        self.tools_button.setEnabled(not self._busy)
        self._append_log(f"Tools: {message}")
        self._validate_form()

    def _on_tools_failed(self, message: str) -> None:
        self._tools_checked = True
        self._tools_ready = False
        self._tools_message = "Java or tools are not ready."
        self.tools_detail.setText(message.splitlines()[0])
        self.tools_detail.show()
        self.tools_button.setText("Retry tools")
        self.tools_button.setEnabled(not self._busy)
        self._append_log(f"Tools error: {message}")
        self._validate_form()

    def _on_tools_finished(self) -> None:
        worker = self._tools_worker
        self._tools_worker = None
        if worker is not None and worker.isRunning():
            worker.wait(1000)

    # ------------------------------------------------------------------ repack
    def repack(self) -> None:
        if self._busy:
            return
        source = self._input_path()
        if source is None:
            return
        if self._info is None:
            self._set_footer_error("Inspect the package before repacking.")
            return
        package = self.package_edit.text().strip()
        try:
            build_rename_plan(package, old_package=self._info.package_name or OLD_PACKAGE)
        except ValueError as exc:
            self._set_footer_error(str(exc))
            self.package_edit.setFocus()
            return
        password_ok, password_message = self._validate_password()
        if not password_ok:
            self._set_footer_error(password_message)
            self.password_edit.setFocus()
            return
        name_ok, icon_ok = self._validate_appearance()
        if not name_ok:
            self._set_footer_error("Fix the app name.")
            self.app_name_edit.setFocus()
            return
        if not icon_ok:
            self._set_footer_error("Choose a valid app icon.")
            self.icon_edit.setFocus()
            return
        server1_ok, server2_ok = self._validate_servers()
        if not server1_ok:
            self._set_footer_error("Fix the Server 1 endpoint.")
            self.server1_edit.setFocus()
            return
        if not server2_ok:
            self._set_footer_error("Fix the Server 2 endpoint.")
            self.server2_edit.setFocus()
            return
        app_name = self.app_name_edit.text().strip()
        icon_text = self.icon_edit.text().strip()
        icon_path = Path(icon_text) if icon_text else None
        server1 = self.server1_edit.text().strip()
        server2 = self.server2_edit.text().strip()
        password = self.password_edit.text()
        output_text = self.output_edit.text().strip()
        output = Path(output_text) if output_text else source.parent / "output"
        if output.exists() and output.is_file():
            self._set_footer_error("Choose an output folder, not a file.")
            return
        keystore_text = self.keystore_edit.text().strip()
        keystore_path = Path(keystore_text) if keystore_text else None
        if keystore_path is not None and keystore_path.exists() and keystore_path.is_dir():
            self._set_footer_error("Choose a keystore file, not a folder.")
            return
        alias = self.alias_edit.text().strip() or DEFAULT_KEYSTORE_ALIAS
        request = RepackRequest(
            input_path=source,
            output_dir=output,
            new_package=package,
            app_name=app_name,
            icon_path=icon_path,
            server1=server1,
            server2=server2,
            keystore_path=keystore_path,
            keystore_password=password,
            keystore_alias=alias,
        )
        self._result = None
        self._sticky_status = ""
        self._outcome = ""
        self.result_card.hide()
        # A previous run may have left the log expanded; collapse it so the new
        # run starts on the progress view instead of a stale log.
        self.details_toggle.setChecked(False)
        self.progress_card.show()
        self.progress.setProperty("state", "")
        _repolish(self.progress)
        self._reset_stages()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status.setText("Starting repack...")
        self.log.clear()
        self.details_hint.clear()
        self._cancel_event = threading.Event()
        self._set_busy(True, cancellable=True)
        self._start_worker(
            lambda progress, log: self._repack_worker(request, progress, log, self._cancel_event),
            self._on_repacked,
            self._on_repack_failed,
        )

    def _repack_worker(
        self,
        request: RepackRequest,
        progress: Progress,
        log: LogLine,
        cancel_event: threading.Event | None,
    ) -> RepackResult:
        result = self._repack_service.repack(request, progress, log, cancel_event=cancel_event)
        log("")
        log("Patches:")
        for line in result.patches.to_lines():
            log(line)
        log("")
        for line in result.verification.to_lines():
            log(line)
        return result

    def _on_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self.status.setText(message)
        self._update_stages(value)

    def _on_repacked(self, result: object) -> None:
        if not isinstance(result, RepackResult):
            return
        self._result = result
        self._cancel_event = None
        self._set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self._mark_all_done()
        self._sticky_status = "APK ready. Open the folder or repack another."
        self.status.setText(self._sticky_status)
        self._append_log("APK ready.")
        self._show_result(
            "success",
            "APK ready",
            str(result.output_apk),
            output=result.output_apk,
        )
        self._save_settings()

    def _on_repack_failed(self, message: str) -> None:
        self._cancel_event = None
        self._set_busy(False)
        self.progress.setRange(0, 100)
        self._mark_failed()
        self._sticky_status = "Repack failed. Review the details or try again."
        self.status.setText(self._sticky_status)
        self._append_log(f"ERROR: {message}")
        self._show_result("error", "Repack failed", message.splitlines()[0])

    def cancel_repack(self) -> None:
        if self._cancel_event is None:
            return
        self._cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.status.setText("Cancelling...")
        self._append_log("Cancel requested.")

    def _on_canceled(self) -> None:
        self._cancel_event = None
        self._set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._mark_canceled()
        self._sticky_status = "Repack canceled. Adjust and try again."
        self.status.setText(self._sticky_status)
        self._append_log("Repack canceled; partial files removed.")
        self._show_result(
            "neutral",
            "Repack canceled",
            "No output was produced. Partial files were removed.",
        )

    def _start_worker(self, func, on_success, on_failed) -> None:
        worker = FunctionWorker(func, self)
        worker.progress.connect(self._on_progress)
        worker.log.connect(self._append_log)
        worker.succeeded.connect(on_success)
        worker.failed.connect(on_failed)
        worker.canceled.connect(self._on_canceled)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None and worker.isRunning():
            # The finished signal is emitted just before the thread unwinds.
            # Wait here so the parent widget never destroys a live QThread.
            worker.wait(1000)
        if not self._busy:
            self._validate_form()

    # ------------------------------------------------------------------- state
    def _set_busy(self, busy: bool, cancellable: bool = False) -> None:
        self._busy = busy
        for widget in (
            self.input_edit,
            self.input_button,
            self.inspect_button,
            self.output_edit,
            self.output_button,
            self.package_edit,
            self.app_name_edit,
            self.icon_edit,
            self.icon_button,
            self.icon_clear,
            self.server1_edit,
            self.server2_edit,
            self.keystore_edit,
            self.keystore_button,
            self.password_edit,
            self.password_toggle,
            self.alias_edit,
            self.advanced_button,
            self.tools_button,
        ):
            widget.setEnabled(not busy)
        if busy and cancellable:
            self.repack_button.setText("Repacking...")
        else:
            self._update_primary_label()
        self.repack_button.setEnabled(False if busy else self.repack_button.isEnabled())
        self.cancel_button.setVisible(busy and cancellable)
        self.cancel_button.setEnabled(busy and cancellable)
        if not busy:
            self.inspect_button.setText("Refresh info")
            self._validate_form()

    def _update_primary_label(self) -> None:
        # The footer holds the only primary button, so its label has to name the
        # next step for the current outcome.
        labels = {"success": "Repack another", "error": "Try again", "neutral": "Try again"}
        self.repack_button.setText(labels.get(self._outcome, "Repack APK"))

    def is_busy(self) -> bool:
        return self._busy

    def shutdown(self) -> None:
        if self._tools_timer is not None:
            self._tools_timer.stop()
        if self._cancel_event is not None:
            self._cancel_event.set()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)
        if self._tools_worker is not None and self._tools_worker.isRunning():
            self._tools_worker.wait(3000)
        self._worker = None
        self._tools_worker = None

    def closeEvent(self, event: QCloseEvent) -> None:
        self.shutdown()
        super().closeEvent(event)

    # ----------------------------------------------------------------- results
    def _show_result(
        self,
        state: str,
        title: str,
        detail: str,
        output: Path | None = None,
    ) -> None:
        self.result_card.setProperty("state", state)
        _repolish(self.result_card)
        titles = {
            "success": "resultSuccess",
            "error": "resultError",
            "neutral": "resultNeutral",
        }
        self.result_title.setObjectName(titles.get(state, "resultNeutral"))
        self.result_title.setText(title)
        _repolish(self.result_title)
        self.result_detail.setText(detail)
        self._outcome = state
        self.open_output_button.setVisible(output is not None)
        self.copy_output_button.setVisible(output is not None)
        self.progress.setProperty("state", state)
        _repolish(self.progress)
        self._update_primary_label()
        self.result_card.show()
        if self._right_scroll is not None:
            QTimer.singleShot(0, lambda: self._right_scroll.ensureWidgetVisible(self.result_card))

    def _open_output(self) -> None:
        if self._result is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._result.output_apk.parent)))

    def _copy_output(self) -> None:
        if self._result is None:
            return
        QGuiApplication.clipboard().setText(str(self._result.output_apk))
        self.status.setText("Output path copied.")

    # ----------------------------------------------------------------- details
    def _toggle_details(self, checked: bool) -> None:
        self.details_panel.setVisible(checked)
        self.details_toggle.setText("Hide details" if checked else "Show details")
        if checked and self._right_scroll is not None:
            QTimer.singleShot(0, lambda: self._right_scroll.ensureWidgetVisible(self.details_panel))

    def _copy_details(self) -> None:
        widget = self.details_tabs.currentWidget()
        if isinstance(widget, QPlainTextEdit):
            QGuiApplication.clipboard().setText(widget.toPlainText())
            self.details_hint.setText("Copied to clipboard.")

    def _append_log(self, line: str) -> None:
        self.log.appendPlainText(line)

    def show_help(self) -> None:
        QMessageBox.information(
            self,
            "What changes",
            "The repackager moves the application id, Java classes, manifest, "
            "resources, native package strings, and JNI symbols to the new "
            "application id.\n\n"
            "Existing app data under the old package is not migrated. The output "
            "APK is signed with the selected release keystore. Keep the same "
            "keystore for every release so updates can replace the previous build.",
        )

    # ------------------------------------------------------------------ stages
    def _reset_stages(self) -> None:
        for status in self.stage_status.values():
            self._set_stage(status, "Pending", "stagePending")

    def _mark_all_done(self) -> None:
        for status in self.stage_status.values():
            self._set_stage(status, "Done", "stageDone")

    def _mark_failed(self) -> None:
        running = self._first_stage("Running")
        if running is None:
            running = STAGES[0]
        for name, status in self.stage_status.items():
            if name == running:
                self._set_stage(status, "Failed", "stageFailed")
            elif status.text() == "Done":
                continue
            else:
                self._set_stage(status, "Pending", "stagePending")

    def _mark_canceled(self) -> None:
        running = self._first_stage("Running")
        if running is None:
            running = STAGES[0]
        for name, status in self.stage_status.items():
            if name == running:
                self._set_stage(status, "Canceled", "stagePending")
            elif status.text() == "Done":
                continue
            else:
                self._set_stage(status, "Pending", "stagePending")

    def _first_stage(self, text: str) -> str | None:
        for name, status in self.stage_status.items():
            if status.text() == text:
                return name
        return None

    def _set_stage(self, label: QLabel, text: str, object_name: str) -> None:
        label.setText(text)
        label.setObjectName(object_name)
        _repolish(label)

    def _update_stages(self, percent: int) -> None:
        if percent >= 100:
            self._mark_all_done()
            return
        if percent >= 95:
            index = 6
        elif percent >= 84:
            index = 5
        elif percent >= 72:
            index = 4
        elif percent >= 60:
            index = 3
        elif percent >= 50:
            index = 2
        elif percent >= 30:
            index = 1
        elif percent >= 12:
            index = 0
        else:
            index = -1
        for position, status in enumerate(self.stage_status.values()):
            if position < index:
                self._set_stage(status, "Done", "stageDone")
            elif position == index:
                self._set_stage(status, "Running", "stageRunning")
            else:
                self._set_stage(status, "Pending", "stagePending")

    def _save_settings(self) -> None:
        if self._settings_service is None:
            return
        try:
            self._settings_service.save_repack_settings(
                self.output_edit.text().strip(),
                self.keystore_edit.text().strip(),
                self.alias_edit.text().strip() or DEFAULT_KEYSTORE_ALIAS,
            )
        except OSError as exc:
            logger.warning("could not save repack settings: %s", exc)
