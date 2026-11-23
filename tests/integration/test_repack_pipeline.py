import os
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from pyaxmlparser.core import APK

from cloneclient.infrastructure.manifest import ANDROID_NS, read_manifest, read_manifest_xml
from cloneclient.services.repack_service import RepackRequest, RepackService
from cloneclient.shared.constants import NEW_PACKAGE, OLD_PACKAGE, OLD_PACKAGE_PATH

pytestmark = pytest.mark.slow


def _xapk() -> Path:
    configured = os.environ.get("CLONECLIENT_XAPK")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / ".cache" / "Growtopia_5.62_dev (3).xapk"


def test_repack_pipeline_end_to_end(tmp_path: Path) -> None:
    if os.environ.get("CLONECLIENT_RUN_SLOW") != "1":
        pytest.skip("set CLONECLIENT_RUN_SLOW=1 to run the slow end-to-end test")
    source = _xapk()
    if not source.exists():
        pytest.skip(f"XAPK not found: {source}")
    icon = tmp_path / "icon.png"
    Image.new("RGBA", (256, 256), (20, 120, 200, 255)).save(icon)
    app_name = "Clone Test"
    server1 = "www.example001.com"
    server2 = "www.example002.com"

    result = RepackService().repack(
        RepackRequest(
            input_path=source,
            output_dir=tmp_path / "out",
            app_name=app_name,
            icon_path=icon,
            server1=server1,
            server2=server2,
            keystore_path=tmp_path / "release.jks",
            keystore_password="testpass",
            keystore_alias="test",
        )
    )

    manifest = read_manifest(result.output_apk)
    assert result.output_apk.exists()
    assert result.verification.passed
    assert manifest.package_name == NEW_PACKAGE
    assert manifest.min_sdk == 32
    assert manifest.target_sdk == 37

    manifest_xml = read_manifest_xml(result.output_apk)
    application = ET.fromstring(manifest_xml).find("application")
    assert application is not None
    assert application.get(f"{ANDROID_NS}label") == app_name
    resolved_icon = APK(str(result.output_apk)).get_app_icon()
    assert resolved_icon is not None
    assert resolved_icon.startswith("res/mipmap-")
    assert resolved_icon.endswith("/cloneclient_icon.png")

    with zipfile.ZipFile(result.output_apk) as archive:
        dex_old = 0
        for name in archive.namelist():
            if re.fullmatch(r"classes\d*\.dex", name):
                data = archive.read(name)
                dex_old += data.count(OLD_PACKAGE.encode())
                dex_old += data.count(OLD_PACKAGE_PATH.encode())
        assert dex_old == 0
        icon_entries = [
            name
            for name in archive.namelist()
            if name.startswith("res/mipmap-") and name.endswith("/cloneclient_icon.png")
        ]
        assert len(icon_entries) == 5
        library = archive.read("lib/arm64-v8a/libgrowtopia.so")
        assert OLD_PACKAGE.encode() not in library
        assert b"com.rtsoft." not in library
        assert b"com/rtsoft/growtopia" not in library
        assert b"Java_com_dev_1rt_growtopia_" in library
        assert b"www.growtopia1.com" not in library
        assert b"www.growtopia2.com" not in library
        assert server1.encode() in library
        assert server2.encode() in library
