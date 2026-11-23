"""Verify the repacked APK without trusting the build log."""

from __future__ import annotations

import os
import re
import struct
import tempfile
import threading
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

import lief
from pyaxmlparser.core import APK

from cloneclient.domain.rename import RenamePlan
from cloneclient.domain.verification import CheckResult, VerificationReport
from cloneclient.infrastructure import signer
from cloneclient.infrastructure.appearance import (
    ICON_REFERENCE,
    ICON_RESOURCE,
    launcher_elements,
)
from cloneclient.infrastructure.manifest import ANDROID_NS, read_manifest_xml
from cloneclient.infrastructure.toolchain import Toolchain


@dataclass(frozen=True)
class _Layout:
    stored: bool
    aligned: bool


def verify_apk(
    apk_path: Path,
    plan: RenamePlan,
    toolchain: Toolchain,
    cancel_event: threading.Event | None = None,
    expected_app_name: str | None = None,
    expected_icon: bool = False,
    server_replacements: tuple[tuple[str, str], ...] = (),
) -> VerificationReport:
    xml_text = read_manifest_xml(apk_path)
    checks = [
        check_manifest_identity(xml_text, plan),
        check_native(apk_path, plan),
        check_dex(apk_path, plan),
        *check_layout(apk_path),
    ]
    if expected_app_name or expected_icon:
        checks.append(
            check_manifest_appearance(apk_path, xml_text, expected_app_name, expected_icon)
        )
    if server_replacements:
        checks.append(check_server_strings(apk_path, server_replacements))
    ok, output = signer.verify(apk_path, toolchain, cancel_event=cancel_event)
    detail = "signature and zipalign verified" if ok else _tail(output)
    checks.append(CheckResult("signature", ok, detail))
    return VerificationReport(tuple(checks))


def check_manifest_identity(xml_text: str, plan: RenamePlan) -> CheckResult:
    root = ET.fromstring(xml_text)
    problems: list[str] = []
    package = root.attrib.get("package")
    if package != plan.new_package:
        problems.append(f"package={package}")
    old_dot = xml_text.count(plan.old_package)
    old_path = xml_text.count(plan.old_path)
    if old_dot or old_path:
        problems.append(f"old manifest references={old_dot + old_path}")
    if problems:
        return CheckResult("manifest identity", False, "; ".join(problems[:5]))
    return CheckResult(
        "manifest identity",
        True,
        f"package={plan.new_package}; no old references",
    )


def check_manifest_appearance(
    apk_path: Path,
    xml_text: str,
    expected_app_name: str | None,
    expected_icon: bool,
) -> CheckResult:
    root = ET.fromstring(xml_text)
    application = root.find("application")
    problems: list[str] = []
    if application is None:
        return CheckResult("app appearance", False, "missing <application>")
    launchers = launcher_elements(application)
    if expected_app_name:
        label = application.get(f"{ANDROID_NS}label")
        if label != expected_app_name:
            problems.append(f"application label={label}")
        for launcher in launchers:
            value = launcher.get(f"{ANDROID_NS}label")
            if value is not None and value != expected_app_name:
                problems.append(f"launcher label={value}")
    if expected_icon:
        resolved_icon = _resolve_icon(apk_path)
        icon = application.get(f"{ANDROID_NS}icon")
        if not _icon_matches(icon, resolved_icon):
            problems.append(f"application icon={icon}")
        for launcher in launchers:
            value = launcher.get(f"{ANDROID_NS}icon")
            if value is not None and not _icon_matches(value, resolved_icon):
                problems.append(f"launcher icon={value}")
        with zipfile.ZipFile(apk_path) as archive:
            icons = [
                name
                for name in archive.namelist()
                if name.startswith("res/mipmap-") and name.endswith(f"/{ICON_RESOURCE}.png")
            ]
        if not icons:
            problems.append("icon resource missing")
    if problems:
        return CheckResult("app appearance", False, "; ".join(problems[:5]))
    details: list[str] = []
    if expected_app_name:
        details.append(f"label={expected_app_name}")
    if expected_icon:
        details.append(f"icon={ICON_RESOURCE}")
    return CheckResult("app appearance", True, "; ".join(details))


def _resolve_icon(apk_path: Path) -> str | None:
    try:
        return APK(str(apk_path)).get_app_icon()
    except Exception:
        return None


def _icon_matches(value: str | None, resolved: str | None) -> bool:
    if value == ICON_REFERENCE:
        return True
    if not value or not value.startswith("@"):
        return False
    return bool(
        resolved
        and resolved.startswith("res/mipmap-")
        and resolved.endswith(f"/{ICON_RESOURCE}.png")
    )


def check_native(apk_path: Path, plan: RenamePlan) -> CheckResult:
    with zipfile.ZipFile(apk_path) as archive:
        libraries = [name for name in archive.namelist() if name.endswith(".so")]
        if not libraries:
            return CheckResult("native strings", True, "no native libraries")
        old_package = 0
        old_path = 0
        old_partial = 0
        old_jni_literals = 0
        old_dynamic_jni = 0
        new_dynamic_jni = 0
        growtopia_library = False
        partial_path_old = plan.old_partial.replace(".", "/").encode("ascii")
        for name in libraries:
            data = archive.read(name)
            if "growtopia" in name.lower():
                growtopia_library = True
            old_package += data.count(plan.old_package.encode("ascii"))
            old_path += data.count(plan.old_path.encode("ascii"))
            old_partial += data.count(plan.old_partial.encode("ascii"))
            old_partial += data.count(partial_path_old)
            old_literals = data.count(plan.old_jni_prefix.encode("ascii"))
            new_literals = data.count(plan.new_jni_prefix.encode("ascii"))
            old_jni_literals += old_literals
            if old_literals or new_literals:
                old_dynamic, new_dynamic = _dynamic_jni_counts(data, plan)
                old_dynamic_jni += old_dynamic
                new_dynamic_jni += new_dynamic
    problems: list[str] = []
    if growtopia_library and new_dynamic_jni == 0:
        problems.append("growtopia JNI symbols are missing")
    if old_dynamic_jni:
        problems.append(f"old JNI symbols={old_dynamic_jni}")
    if old_package:
        problems.append(f"old package strings={old_package}")
    if old_path:
        problems.append(f"old path strings={old_path}")
    if old_partial:
        problems.append(f"old prefix strings={old_partial}")
    if problems:
        return CheckResult("native strings", False, "; ".join(problems))
    return CheckResult(
        "native strings",
        True,
        f"new JNI symbols={new_dynamic_jni}; old JNI literals={old_jni_literals}; "
        "old package strings=0",
    )


def _dynamic_jni_counts(data: bytes, plan: RenamePlan) -> tuple[int, int]:
    with tempfile.NamedTemporaryFile(suffix=".so", delete=False) as handle:
        handle.write(data)
        temporary = handle.name
    try:
        binary = lief.ELF.parse(temporary)
    finally:
        os.unlink(temporary)
    if binary is None:
        return 0, 0
    old = sum(1 for symbol in binary.dynamic_symbols if symbol.name.startswith(plan.old_jni_prefix))
    new = sum(1 for symbol in binary.dynamic_symbols if symbol.name.startswith(plan.new_jni_prefix))
    return old, new


def check_server_strings(
    apk_path: Path,
    replacements: tuple[tuple[str, str], ...],
) -> CheckResult:
    with zipfile.ZipFile(apk_path) as archive:
        libraries = [archive.read(name) for name in archive.namelist() if name.endswith(".so")]
    problems: list[str] = []
    details: list[str] = []
    for index, (old, new) in enumerate(replacements, 1):
        old_bytes = old.encode("ascii")
        new_bytes = new.encode("ascii")
        old_count = sum(data.count(old_bytes) for data in libraries)
        new_count = sum(data.count(new_bytes) for data in libraries)
        if old_count:
            problems.append(f"old server{index}={old_count}")
        if not new_count:
            problems.append(f"new server{index}=missing")
        details.append(f"server{index}={new_count}")
    if problems:
        return CheckResult("server endpoints", False, "; ".join(problems))
    return CheckResult("server endpoints", True, "; ".join(details))


def check_dex(apk_path: Path, plan: RenamePlan) -> CheckResult:
    old_dot = plan.old_package.encode("ascii")
    old_path = plan.old_path.encode("ascii")
    with zipfile.ZipFile(apk_path) as archive:
        names = [name for name in archive.namelist() if re.fullmatch(r"classes\d*\.dex", name)]
        old = 0
        for name in names:
            data = archive.read(name)
            old += data.count(old_dot)
            old += data.count(old_path)
    if old:
        return CheckResult("dex strings", False, f"{old} old references in {len(names)} dex files")
    return CheckResult("dex strings", True, f"no old references in {len(names)} dex files")


def check_layout(apk_path: Path) -> tuple[CheckResult, ...]:
    with zipfile.ZipFile(apk_path) as archive:
        names = ["AndroidManifest.xml", "resources.arsc"]
        names.extend(info.filename for info in archive.infolist() if info.filename.endswith(".so"))
        checks: list[CheckResult] = []
        for name in names:
            try:
                info = archive.getinfo(name)
            except KeyError:
                checks.append(CheckResult(f"layout:{name}", False, "missing"))
                continue
            layout = _read_layout(apk_path, info.header_offset)
            checks.append(
                CheckResult(
                    f"layout:{name}",
                    layout.stored and layout.aligned,
                    f"stored={layout.stored} aligned={layout.aligned}",
                )
            )
        return tuple(checks)


def _read_layout(apk_path: Path, header_offset: int) -> _Layout:
    with apk_path.open("rb") as handle:
        handle.seek(header_offset)
        header = handle.read(30)
    if len(header) != 30 or header[:4] != b"PK\x03\x04":
        return _Layout(stored=False, aligned=False)
    compression = struct.unpack_from("<H", header, 8)[0]
    name_length = struct.unpack_from("<H", header, 26)[0]
    extra_length = struct.unpack_from("<H", header, 28)[0]
    data_offset = header_offset + 30 + name_length + extra_length
    return _Layout(stored=compression == 0, aligned=data_offset % 4 == 0)


def _tail(output: str) -> str:
    lines = output.splitlines()
    return "\n".join(lines[-10:]) if lines else "signature verification failed"
