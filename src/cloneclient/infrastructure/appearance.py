"""Apply a launcher name and icon to a decoded APK tree."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from cloneclient.domain.rename import PatchReport
from cloneclient.infrastructure.manifest import ANDROID_NS
from cloneclient.shared.errors import InputError, PipelineError

ICON_RESOURCE = "cloneclient_icon"
ICON_REFERENCE = f"@mipmap/{ICON_RESOURCE}"
ICON_DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}
ICON_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MIN_ICON_SIZE = 48
LAUNCHER_ACTION = "android.intent.action.MAIN"
LAUNCHER_CATEGORY = "android.intent.category.LAUNCHER"
ANDROID_URI = "http://schemas.android.com/apk/res/android"


def validate_app_name(name: str) -> str:
    value = name.strip()
    if not value:
        return ""
    # A leading @ or ? makes aapt treat the label as a resource reference.
    if value[0] in "@?":
        raise InputError("App name cannot start with @ or ?")
    if any(ord(character) < 32 for character in value):
        raise InputError("App name cannot contain control characters")
    return value


def validate_icon(path: Path) -> tuple[int, int]:
    if not path.is_file():
        raise InputError("App icon file does not exist")
    if path.suffix.lower() not in ICON_SUFFIXES:
        raise InputError("App icon must be a PNG, JPG, or WebP image")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            size = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InputError(f"cannot read app icon: {exc}") from exc
    if min(size) < MIN_ICON_SIZE:
        raise InputError(f"App icon must be at least {MIN_ICON_SIZE}x{MIN_ICON_SIZE} pixels")
    return size


def launcher_elements(application: ET.Element) -> list[ET.Element]:
    elements: list[ET.Element] = []
    for element in application:
        if element.tag not in {"activity", "activity-alias"}:
            continue
        if _has_launcher_intent(element):
            elements.append(element)
    return elements


def apply_appearance(
    decoded_dir: Path,
    app_name: str = "",
    icon_path: Path | None = None,
    report: PatchReport | None = None,
) -> PatchReport:
    result = report if report is not None else PatchReport()
    name = validate_app_name(app_name)
    if not name and icon_path is None:
        return result

    manifest = decoded_dir / "AndroidManifest.xml"
    if not manifest.is_file():
        raise PipelineError("decoded tree has no AndroidManifest.xml")
    if icon_path is not None:
        validate_icon(icon_path)

    ET.register_namespace("android", ANDROID_URI)
    tree = ET.parse(manifest)
    root = tree.getroot()
    application = root.find("application")
    if application is None:
        raise PipelineError("AndroidManifest.xml has no <application>")
    launchers = launcher_elements(application)

    if name:
        _set_label(application, name)
        for launcher in launchers:
            _set_label(launcher, name)
        result.add("AndroidManifest.xml", "app name", 1 + len(launchers), "appearance")

    if icon_path is not None:
        icon_count = _install_icon(decoded_dir, icon_path)
        _set_icon(application)
        for launcher in launchers:
            _set_icon(launcher)
        result.add("AndroidManifest.xml", "app icon", 1 + len(launchers), "appearance")
        result.add("res/mipmap-*", "app icon", icon_count, "appearance")

    ET.indent(tree, space="  ")
    tree.write(manifest, encoding="utf-8", xml_declaration=True)
    return result


def _has_launcher_intent(element: ET.Element) -> bool:
    for intent in element.findall("intent-filter"):
        actions = {action.get(f"{ANDROID_NS}name") for action in intent.findall("action")}
        categories = {category.get(f"{ANDROID_NS}name") for category in intent.findall("category")}
        if LAUNCHER_ACTION in actions and LAUNCHER_CATEGORY in categories:
            return True
    return False


def _set_label(element: ET.Element, name: str) -> None:
    element.set(f"{ANDROID_NS}label", name)


def _set_icon(element: ET.Element) -> None:
    element.set(f"{ANDROID_NS}icon", ICON_REFERENCE)
    element.set(f"{ANDROID_NS}roundIcon", ICON_REFERENCE)


def _install_icon(decoded_dir: Path, icon_path: Path) -> int:
    res = decoded_dir / "res"
    res.mkdir(exist_ok=True)
    count = 0
    with Image.open(icon_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
        for density, size in ICON_DENSITIES.items():
            folder = res / f"mipmap-{density}"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{ICON_RESOURCE}.png"
            fitted = ImageOps.fit(image, (size, size), method=Image.Resampling.LANCZOS)
            fitted.save(target, format="PNG")
            count += 1
    return count
