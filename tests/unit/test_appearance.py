import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from cloneclient.domain.rename import PatchReport
from cloneclient.infrastructure.appearance import (
    ICON_REFERENCE,
    apply_appearance,
    validate_app_name,
    validate_icon,
)
from cloneclient.shared.errors import InputError

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.dev_rt.growtopia">
  <application android:label="@string/app_name"
      android:icon="@mipmap/ic_launcher"
      android:roundIcon="@mipmap/ic_launcher_round">
    <activity android:name=".Main"
        android:label="@string/app_name"
        android:icon="@mipmap/ic_launcher">
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
      </intent-filter>
    </activity>
    <activity android:name=".Settings" android:label="Settings" />
  </application>
</manifest>
"""


def make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "decoded"
    root.mkdir()
    (root / "AndroidManifest.xml").write_text(MANIFEST, encoding="utf-8")
    return root


def make_icon(tmp_path: Path, size: tuple[int, int] = (256, 192)) -> Path:
    path = tmp_path / "icon.png"
    Image.new("RGBA", size, (200, 30, 30, 255)).save(path)
    return path


def read_application(root: Path) -> ET.Element:
    tree = ET.parse(root / "AndroidManifest.xml")
    application = tree.getroot().find("application")
    assert application is not None
    return application


def test_apply_name_and_icon(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    icon = make_icon(tmp_path)
    report = PatchReport()

    apply_appearance(root, "Clone Client", icon, report)

    application = read_application(root)
    assert application.get(f"{ANDROID_NS}label") == "Clone Client"
    assert application.get(f"{ANDROID_NS}icon") == ICON_REFERENCE
    assert application.get(f"{ANDROID_NS}roundIcon") == ICON_REFERENCE
    activities = application.findall("activity")
    assert activities[0].get(f"{ANDROID_NS}label") == "Clone Client"
    assert activities[0].get(f"{ANDROID_NS}icon") == ICON_REFERENCE
    assert activities[1].get(f"{ANDROID_NS}label") == "Settings"
    for density, size in {
        "mdpi": 48,
        "hdpi": 72,
        "xhdpi": 96,
        "xxhdpi": 144,
        "xxxhdpi": 192,
    }.items():
        target = root / "res" / f"mipmap-{density}" / "cloneclient_icon.png"
        assert target.is_file()
        with Image.open(target) as image:
            assert image.size == (size, size)
    assert report.total >= 2


def test_name_only_keeps_icon(tmp_path: Path) -> None:
    root = make_tree(tmp_path)

    apply_appearance(root, "Only Name")

    application = read_application(root)
    assert application.get(f"{ANDROID_NS}label") == "Only Name"
    assert application.get(f"{ANDROID_NS}icon") == "@mipmap/ic_launcher"
    assert not (root / "res").exists()


def test_icon_only_keeps_label(tmp_path: Path) -> None:
    root = make_tree(tmp_path)
    icon = make_icon(tmp_path)

    apply_appearance(root, "", icon)

    application = read_application(root)
    assert application.get(f"{ANDROID_NS}label") == "@string/app_name"
    assert application.get(f"{ANDROID_NS}icon") == ICON_REFERENCE


def test_app_name_rejects_resource_prefix() -> None:
    with pytest.raises(InputError, match="cannot start"):
        validate_app_name("@string/app_name")


def test_icon_validation_rejects_invalid_and_small_files(tmp_path: Path) -> None:
    text = tmp_path / "icon.png"
    text.write_text("not an image", encoding="utf-8")
    with pytest.raises(InputError):
        validate_icon(text)

    small = tmp_path / "small.png"
    Image.new("RGB", (32, 32), "red").save(small)
    with pytest.raises(InputError, match="at least 48"):
        validate_icon(small)
