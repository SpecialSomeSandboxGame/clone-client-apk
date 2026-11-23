import io
import json
import zipfile
from pathlib import Path

from cloneclient.infrastructure.xapk_inspector import inspect
from cloneclient.shared.constants import OLD_JNI_PREFIX, OLD_PACKAGE


def _inner_apk(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_inspect_xapk_inventory_and_occurrences(tmp_path: Path) -> None:
    base = _inner_apk(
        {
            "classes.dex": b"\x00" + OLD_PACKAGE.encode() + b"\x00",
            "assets/config.txt": b"path=com/rtsoft/growtopia",
            "lib/arm64-v8a/libgrowtopia.so": (
                b"\x00" + OLD_PACKAGE.encode() + b"\x00" + OLD_JNI_PREFIX.encode() + b"Main\x00"
            ),
            "resources.arsc": OLD_PACKAGE.encode("utf-16le"),
        }
    )
    abi = _inner_apk({"lib/arm64-v8a/libx.so": b"binary"})
    language = _inner_apk({"resources.arsc": b"language"})
    xapk = tmp_path / "sample.xapk"
    with zipfile.ZipFile(xapk, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "package_name": OLD_PACKAGE,
                    "version_name": "5.62",
                    "version_code": "428",
                    "min_sdk_version": "32",
                    "target_sdk_version": "37",
                }
            ),
        )
        archive.writestr("com.rtsoft.growtopia.apk", base)
        archive.writestr("config.arm64_v8a.apk", abi)
        archive.writestr("config.en.apk", language)

    info = inspect(xapk)

    assert info.is_xapk is True
    assert info.package_name == OLD_PACKAGE
    assert info.version_name == "5.62"
    assert info.min_sdk == 32
    assert info.target_sdk == 37
    assert info.split_count == 3
    assert info.abis == ("arm64_v8a",)
    assert info.languages == ("en",)
    assert info.has_obb is False
    assert any(occurrence.pattern == "jni" for occurrence in info.occurrences)
    assert any(occurrence.pattern == "utf-16le" for occurrence in info.occurrences)
