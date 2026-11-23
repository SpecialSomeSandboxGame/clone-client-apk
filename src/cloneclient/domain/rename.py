"""Pure rename plan and patch report models."""

from __future__ import annotations

from dataclasses import dataclass, field

from cloneclient.domain.apk import native_patch_fits, validate_application_id
from cloneclient.shared.constants import OLD_PACKAGE


def jni_prefix(package: str) -> str:
    """Return the JNI symbol prefix for a Java package.

    JNI encodes underscores as ``_1`` before replacing dots with underscores,
    so a package such as ``com.dev_rt.growtopia`` becomes
    ``Java_com_dev_1rt_growtopia_``.
    """
    encoded = package.replace("_", "_1").replace(".", "_")
    return f"Java_{encoded}_"


def partial_prefix(package: str) -> str:
    """Return the package minus its final segment, with a trailing dot.

    The native game code builds class names from this prefix and a suffix, so
    leaving it unchanged keeps a stale package name alive even when every full
    package string was replaced.
    """
    head, separator, _ = package.rpartition(".")
    if not separator:
        return f"{package}."
    return f"{head}."


@dataclass(frozen=True)
class RenamePlan:
    old_package: str
    new_package: str
    old_path: str
    new_path: str
    old_jni_prefix: str
    new_jni_prefix: str
    old_partial: str
    new_partial: str

    @property
    def native_length_ok(self) -> bool:
        return native_patch_fits(self.old_package, self.new_package) and native_patch_fits(
            self.old_partial, self.new_partial
        )


def build_rename_plan(new_package: str, old_package: str = OLD_PACKAGE) -> RenamePlan:
    validate_application_id(new_package)
    old_partial = partial_prefix(old_package)
    new_partial = partial_prefix(new_package)
    if not native_patch_fits(old_package, new_package):
        raise ValueError(
            f"The new application id must be exactly {len(old_package)} characters "
            "to keep the native strings in place"
        )
    if not native_patch_fits(old_partial, new_partial):
        raise ValueError(
            "The new application id must keep the same segment split as the original "
            f"so the native prefix stays {len(old_partial)} characters"
        )
    return RenamePlan(
        old_package=old_package,
        new_package=new_package,
        old_path=old_package.replace(".", "/"),
        new_path=new_package.replace(".", "/"),
        old_jni_prefix=jni_prefix(old_package),
        new_jni_prefix=jni_prefix(new_package),
        old_partial=old_partial,
        new_partial=new_partial,
    )


@dataclass(frozen=True)
class PatchEntry:
    file: str
    pattern: str
    count: int
    method: str


@dataclass
class PatchReport:
    entries: list[PatchEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, file: str, pattern: str, count: int, method: str) -> None:
        if count:
            self.entries.append(PatchEntry(file=file, pattern=pattern, count=count, method=method))

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def total(self) -> int:
        return sum(entry.count for entry in self.entries)

    def to_lines(self) -> list[str]:
        lines = [
            f"{entry.count:4d}  {entry.method:8s}  {entry.pattern}  {entry.file}"
            for entry in self.entries
        ]
        lines.extend(f"warning: {message}" for message in self.warnings)
        return lines
