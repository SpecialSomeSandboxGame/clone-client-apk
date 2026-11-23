"""Pure models and validation for APK and XAPK inspection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ABIS = frozenset(
    {
        "armeabi",
        "armeabi_v7a",
        "arm64_v8a",
        "x86",
        "x86_64",
        "mips",
        "mips64",
    }
)
DENSITIES = frozenset(
    {
        "ldpi",
        "mdpi",
        "tvdpi",
        "hdpi",
        "xhdpi",
        "xxhdpi",
        "xxxhdpi",
        "nodpi",
        "anydpi",
    }
)
LANGUAGE = re.compile(r"^[a-z]{2,3}(-r[A-Z]{2})?$")
APPLICATION_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")


def validate_application_id(value: str) -> str:
    """Return value when it is a valid Android applicationId.

    Hyphens are rejected by Android even though domain names commonly contain
    them, so the UI must surface the error before any work starts.
    """
    if not APPLICATION_ID.fullmatch(value):
        raise ValueError(
            "applicationId must have at least two dot-separated segments; "
            "each segment starts with a letter and contains only letters, digits, or underscores"
        )
    return value


def native_patch_fits(old: str, new: str) -> bool:
    """Native strings can be replaced in place only at an identical byte length."""
    if not old.isascii() or not new.isascii():
        return False
    return len(old) == len(new)


@dataclass(frozen=True)
class SplitInfo:
    name: str
    size: int
    kind: str
    qualifier: str


@dataclass(frozen=True)
class FileOccurrence:
    container: str
    path: str
    pattern: str
    count: int


@dataclass(frozen=True)
class ApkInfo:
    source: Path
    is_xapk: bool
    package_name: str | None
    version_name: str | None
    version_code: str | None
    min_sdk: int | None
    target_sdk: int | None
    splits: tuple[SplitInfo, ...]
    abis: tuple[str, ...]
    densities: tuple[str, ...]
    languages: tuple[str, ...]
    has_obb: bool
    total_size: int
    occurrences: tuple[FileOccurrence, ...]

    @property
    def split_count(self) -> int:
        return len(self.splits)


def classify_split(name: str) -> tuple[str, str]:
    """Return (kind, qualifier) for an APK entry inside an XAPK."""
    stem = Path(name).stem
    if not stem.startswith("config."):
        return "base", ""
    qualifier = stem.removeprefix("config.")
    if qualifier in ABIS:
        return "abi", qualifier
    if qualifier in DENSITIES:
        return "density", qualifier
    if LANGUAGE.fullmatch(qualifier):
        return "language", qualifier
    return "other", qualifier
