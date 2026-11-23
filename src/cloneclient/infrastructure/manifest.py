"""Parse binary Android manifests for diagnostics and verification."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from pyaxmlparser.axmlprinter import AXMLPrinter

from cloneclient.shared.errors import InputError

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


@dataclass(frozen=True)
class ManifestInfo:
    package_name: str | None
    version_name: str | None
    version_code: str | None
    min_sdk: int | None
    target_sdk: int | None
    split: str | None


def read_manifest_xml(apk: Path) -> str:
    try:
        with zipfile.ZipFile(apk) as archive:
            data = archive.read("AndroidManifest.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise InputError(f"cannot read AndroidManifest.xml from {apk}") from exc
    try:
        return AXMLPrinter(data).get_xml().decode("utf-8", errors="replace")
    except Exception as exc:
        raise InputError(f"cannot decode AndroidManifest.xml from {apk}: {exc}") from exc


def parse_manifest(data: bytes) -> ManifestInfo:
    try:
        xml_text = AXMLPrinter(data).get_xml().decode("utf-8", errors="replace")
        root = ET.fromstring(xml_text)
    except Exception as exc:
        raise InputError(f"cannot parse AndroidManifest.xml: {exc}") from exc
    uses_sdk = root.find("uses-sdk")
    return ManifestInfo(
        package_name=root.attrib.get("package"),
        version_name=root.attrib.get(f"{ANDROID_NS}versionName"),
        version_code=root.attrib.get(f"{ANDROID_NS}versionCode"),
        min_sdk=_optional_int(
            uses_sdk.attrib.get(f"{ANDROID_NS}minSdkVersion") if uses_sdk is not None else None
        ),
        target_sdk=_optional_int(
            uses_sdk.attrib.get(f"{ANDROID_NS}targetSdkVersion") if uses_sdk is not None else None
        ),
        split=root.attrib.get("split"),
    )


def read_manifest(apk: Path) -> ManifestInfo:
    try:
        with zipfile.ZipFile(apk) as archive:
            data = archive.read("AndroidManifest.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise InputError(f"cannot read AndroidManifest.xml from {apk}") from exc
    return parse_manifest(data)


def _optional_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
