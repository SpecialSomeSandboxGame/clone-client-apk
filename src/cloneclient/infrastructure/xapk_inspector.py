"""Inspect XAPK and APK files without decoding the whole package."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from cloneclient.domain.apk import ApkInfo, FileOccurrence, SplitInfo, classify_split
from cloneclient.infrastructure.manifest import parse_manifest
from cloneclient.shared.constants import OLD_JNI_PREFIX, OLD_PACKAGE, OLD_PACKAGE_PATH
from cloneclient.shared.errors import InputError

TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".dat",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".lua",
    ".properties",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
MAX_ASSET_BYTES = 2_000_000


def inspect(path: Path) -> ApkInfo:
    suffix = path.suffix.lower()
    if suffix == ".xapk":
        return _inspect_xapk(path)
    if suffix == ".apk":
        return _inspect_apk(path)
    raise InputError("select an .xapk or .apk file")


def _inspect_xapk(path: Path) -> ApkInfo:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise InputError(f"cannot open XAPK: {path}") from exc
    with archive:
        if "manifest.json" not in archive.namelist():
            raise InputError("XAPK has no manifest.json")
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InputError("XAPK manifest.json is not valid JSON") from exc
        apk_names = [name for name in archive.namelist() if name.lower().endswith(".apk")]
        if not apk_names:
            raise InputError("XAPK contains no APK files")
        splits = []
        for name in apk_names:
            info = archive.getinfo(name)
            kind, qualifier = classify_split(name)
            splits.append(SplitInfo(name=name, size=info.file_size, kind=kind, qualifier=qualifier))
        occurrences: list[FileOccurrence] = []
        for name in apk_names:
            try:
                with zipfile.ZipFile(io.BytesIO(archive.read(name))) as inner:
                    occurrences.extend(_scan_apk_archive(inner, name))
            except (OSError, zipfile.BadZipFile):
                raise InputError(f"XAPK member is not a readable APK: {name}") from None
        return ApkInfo(
            source=path,
            is_xapk=True,
            package_name=manifest.get("package_name"),
            version_name=_as_text(manifest.get("version_name")),
            version_code=_as_text(manifest.get("version_code")),
            min_sdk=_as_int(manifest.get("min_sdk_version")),
            target_sdk=_as_int(manifest.get("target_sdk_version")),
            splits=tuple(splits),
            abis=tuple(sorted({s.qualifier for s in splits if s.kind == "abi"})),
            densities=tuple(sorted({s.qualifier for s in splits if s.kind == "density"})),
            languages=tuple(sorted({s.qualifier for s in splits if s.kind == "language"})),
            has_obb=any(name.lower().endswith(".obb") for name in archive.namelist()),
            total_size=path.stat().st_size,
            occurrences=tuple(occurrences),
        )


def _inspect_apk(path: Path) -> ApkInfo:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise InputError(f"cannot open APK: {path}") from exc
    with archive:
        try:
            manifest = parse_manifest(archive.read("AndroidManifest.xml"))
        except KeyError as exc:
            raise InputError("APK has no AndroidManifest.xml") from exc
        if manifest.package_name is None:
            raise InputError("APK manifest has no package name")
        names = archive.namelist()
        abis = sorted(
            {
                name.split("/")[1]
                for name in names
                if name.startswith("lib/") and name.count("/") >= 2
            }
        )
        split_kind = "split" if manifest.split else "base"
        return ApkInfo(
            source=path,
            is_xapk=False,
            package_name=manifest.package_name,
            version_name=manifest.version_name,
            version_code=manifest.version_code,
            min_sdk=manifest.min_sdk,
            target_sdk=manifest.target_sdk,
            splits=(
                SplitInfo(
                    name=path.name,
                    size=path.stat().st_size,
                    kind=split_kind,
                    qualifier=manifest.split or "",
                ),
            ),
            abis=tuple(abis),
            densities=(),
            languages=(),
            has_obb=any(name.lower().endswith(".obb") for name in names),
            total_size=path.stat().st_size,
            occurrences=tuple(_scan_apk_archive(archive, path.name)),
        )


def _scan_apk_archive(archive: zipfile.ZipFile, container: str) -> list[FileOccurrence]:
    occurrences: list[FileOccurrence] = []
    for info in archive.infolist():
        name = info.filename
        if not _should_scan(name, info.file_size):
            continue
        try:
            data = archive.read(name)
        except (OSError, RuntimeError, zipfile.BadZipFile):
            continue
        for label, pattern in _patterns_for(name):
            count = data.count(pattern)
            if count:
                occurrences.append(
                    FileOccurrence(
                        container=container,
                        path=name,
                        pattern=label,
                        count=count,
                    )
                )
    return occurrences


def _should_scan(name: str, size: int) -> bool:
    if name.endswith((".dex", ".so")):
        return True
    if name in ("AndroidManifest.xml", "resources.arsc"):
        return True
    if name.startswith("assets/") and Path(name).suffix.lower() in TEXT_SUFFIXES:
        return size <= MAX_ASSET_BYTES
    return False


def _patterns_for(name: str) -> tuple[tuple[str, bytes], ...]:
    patterns: list[tuple[str, bytes]] = [
        ("utf-8", OLD_PACKAGE.encode()),
        ("path", OLD_PACKAGE_PATH.encode()),
    ]
    if name in ("AndroidManifest.xml", "resources.arsc"):
        patterns.extend(
            [
                ("utf-16le", OLD_PACKAGE.encode("utf-16le")),
                ("utf-16be", OLD_PACKAGE.encode("utf-16be")),
            ]
        )
    if name.endswith(".so"):
        patterns.append(("jni", OLD_JNI_PREFIX.encode()))
    return tuple(patterns)


def _as_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _as_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
