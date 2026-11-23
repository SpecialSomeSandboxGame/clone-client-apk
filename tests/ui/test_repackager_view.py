import time
from pathlib import Path

from PIL import Image

from cloneclient.domain.apk import ApkInfo
from cloneclient.services.inspect_service import InspectService
from cloneclient.services.repack_service import RepackService
from cloneclient.shared.constants import (
    KEY_PASSWORD_MIN_MESSAGE,
    NEW_PACKAGE,
    OLD_PACKAGE,
)
from cloneclient.shared.errors import CancelledError
from cloneclient.ui.repackager_view import RepackagerView


def _info(source: Path) -> ApkInfo:
    return ApkInfo(
        source=source,
        package_name=OLD_PACKAGE,
        version_name="5.62",
        version_code="428",
        min_sdk=32,
        target_sdk=37,
        splits=(),
        abis=("arm64_v8a",),
        densities=("mdpi",),
        languages=("en",),
        has_obb=False,
        total_size=1024,
        occurrences=(),
        is_xapk=False,
    )


def _view(tmp_path: Path, repack_service=None) -> RepackagerView:
    view = RepackagerView(
        InspectService(),
        repack_service or RepackService(),
        settings_service=None,
        check_tools_on_start=False,
    )
    view._tools_ready = True
    view._tools_checked = True
    source = tmp_path / "input.xapk"
    source.write_bytes(b"x")
    view.input_edit.setText(str(source))
    view._info = _info(source)
    view.output_edit.setText(str(tmp_path / "out"))
    view.password_edit.setText("secret")
    view._validate_form()
    return view


def test_repackager_validates_application_id(qtbot, tmp_path: Path) -> None:
    view = _view(tmp_path)
    qtbot.addWidget(view)

    view.package_edit.setText("bad-id")
    view._validate_form()
    assert not view.package_error.isHidden()
    assert not view.repack_button.isEnabled()

    view.package_edit.setText(NEW_PACKAGE)
    view._validate_form()
    assert view.repack_button.isEnabled()


def test_repackager_requires_same_package_length(qtbot, tmp_path: Path) -> None:
    view = _view(tmp_path)
    qtbot.addWidget(view)

    view.package_edit.setText("com.devrt.growtopia")
    view._validate_form()
    assert "exactly 20" in view.package_error.text()
    assert not view.repack_button.isEnabled()

    view.package_edit.setText(NEW_PACKAGE)
    view._validate_form()
    assert view.repack_button.isEnabled()


def test_repackager_requires_six_character_password(qtbot, tmp_path: Path) -> None:
    view = _view(tmp_path)
    qtbot.addWidget(view)

    view.password_edit.setText("12345")
    view._validate_form()
    assert not view.password_error.isHidden()
    assert view.password_error.text() == KEY_PASSWORD_MIN_MESSAGE
    assert not view.repack_button.isEnabled()

    view.password_edit.setText("123456")
    view._validate_form()
    assert view.password_error.isHidden()
    assert view.repack_button.isEnabled()


def test_repackager_requires_valid_app_name(qtbot, tmp_path: Path) -> None:
    view = _view(tmp_path)
    qtbot.addWidget(view)

    view.app_name_edit.setText("@bad")
    view._validate_form()
    assert not view.app_name_error.isHidden()
    assert not view.repack_button.isEnabled()

    view.app_name_edit.setText("Clone Client")
    view._validate_form()
    assert view.repack_button.isEnabled()


def test_repackager_requires_valid_icon(qtbot, tmp_path: Path) -> None:
    view = _view(tmp_path)
    qtbot.addWidget(view)

    bad = tmp_path / "bad.png"
    bad.write_text("not an image", encoding="utf-8")
    view.icon_edit.setText(str(bad))
    view._validate_form()
    assert not view.icon_error.isHidden()
    assert not view.repack_button.isEnabled()
    assert view.icon_preview.isHidden()

    icon = tmp_path / "icon.png"
    Image.new("RGBA", (256, 256), (20, 120, 200, 255)).save(icon)
    view.icon_edit.setText(str(icon))
    view._validate_form()
    assert view.icon_error.isHidden()
    assert view.repack_button.isEnabled()
    assert not view.icon_preview.isHidden()


def test_repackager_validates_server_endpoints(qtbot, tmp_path: Path) -> None:
    view = _view(tmp_path)
    qtbot.addWidget(view)

    view.server1_edit.setText("short")
    view._validate_form()
    assert not view.server1_error.isHidden()
    assert not view.repack_button.isEnabled()

    view.server1_edit.setText("www.example001.com")
    view.server2_edit.setText("www.example002.com")
    view._validate_form()
    assert view.server1_error.isHidden()
    assert view.repack_button.isEnabled()


def test_repackager_passes_appearance_to_service(qtbot, tmp_path: Path) -> None:
    class CaptureRepackService:
        def __init__(self) -> None:
            self.request = None

        def check_tools(self) -> str:
            return "ready"

        def repack(self, request, on_progress=None, on_log=None, cancel_event=None):
            self.request = request
            raise CancelledError("stop")

    service = CaptureRepackService()
    view = _view(tmp_path, service)
    qtbot.addWidget(view)
    icon = tmp_path / "icon.png"
    Image.new("RGBA", (256, 256), (20, 120, 200, 255)).save(icon)
    view.app_name_edit.setText("Clone Client")
    view.icon_edit.setText(str(icon))
    view.server1_edit.setText("www.example001.com")
    view.server2_edit.setText("www.example002.com")
    view._validate_form()
    assert view.repack_button.isEnabled()

    view.repack()
    qtbot.waitUntil(lambda: view._worker is None, timeout=3000)
    view.shutdown()

    assert service.request is not None
    assert service.request.app_name == "Clone Client"
    assert service.request.icon_path == icon
    assert service.request.server1 == "www.example001.com"
    assert service.request.server2 == "www.example002.com"


def test_repackager_cancel_returns_to_idle(qtbot, tmp_path: Path) -> None:
    class SlowRepackService:
        def check_tools(self) -> str:
            return "ready"

        def repack(self, request, on_progress=None, on_log=None, cancel_event=None):
            if on_progress is not None:
                on_progress(12, "Merging")
            while cancel_event is not None and not cancel_event.is_set():
                time.sleep(0.01)
            raise CancelledError("canceled")

    view = _view(tmp_path, SlowRepackService())
    qtbot.addWidget(view)
    view.show()

    view.repack()
    qtbot.waitUntil(lambda: not view.cancel_button.isHidden(), timeout=2000)
    view.cancel_button.click()
    qtbot.waitUntil(lambda: not view.is_busy(), timeout=3000)
    qtbot.waitUntil(lambda: view._worker is None, timeout=3000)
    view.shutdown()

    assert "cancel" in view.status.text().lower()
    assert view.result_title.text() == "Repack canceled"
    assert view.repack_button.isEnabled()
