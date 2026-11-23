import zipfile
from pathlib import Path

from cloneclient.domain.server import SERVER_1
from cloneclient.domain.verification import CheckResult, VerificationReport
from cloneclient.infrastructure.apk_verifier import (
    check_manifest_appearance,
    check_server_strings,
)
from cloneclient.infrastructure.appearance import ICON_REFERENCE


def test_verification_passes_when_all_checks_pass() -> None:
    report = VerificationReport(
        (
            CheckResult("package", True, "com.dev_rt.growtopia"),
            CheckResult("signature", True, "v3"),
        )
    )

    assert report.passed is True
    assert report.failed == ()
    assert report.to_lines()[0] == "verification: PASS"


def test_verification_reports_failures() -> None:
    report = VerificationReport(
        (
            CheckResult("package", False, "old package found"),
            CheckResult("signature", True, "v3"),
        )
    )

    assert report.passed is False
    assert len(report.failed) == 1
    assert report.to_lines()[0] == "verification: FAIL"


def _appearance_xml(label: str) -> str:
    return f"""<manifest xmlns:android="http://schemas.android.com/apk/res/android">
  <application android:label="{label}" android:icon="{ICON_REFERENCE}">
    <activity android:name=".Main" android:label="{label}">
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
      </intent-filter>
    </activity>
  </application>
</manifest>"""


def test_manifest_appearance_check(tmp_path: Path) -> None:
    apk = tmp_path / "app.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("res/mipmap-mdpi/cloneclient_icon.png", b"icon")

    assert check_manifest_appearance(
        apk, _appearance_xml("Clone Client"), "Clone Client", True
    ).passed
    assert not check_manifest_appearance(
        apk, _appearance_xml("Old Name"), "Clone Client", True
    ).passed


def test_server_strings_check(tmp_path: Path) -> None:
    apk = tmp_path / "app.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr(
            "lib/arm64-v8a/libgrowtopia.so",
            b"www.example001.com\x00",
        )

    assert check_server_strings(apk, ((SERVER_1, "www.example001.com"),)).passed
    assert not check_server_strings(apk, ((SERVER_1, "www.example002.com"),)).passed
