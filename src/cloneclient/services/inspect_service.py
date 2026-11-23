"""Inspect an APK or XAPK and render a stable diagnostics report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from cloneclient.domain.apk import ApkInfo
from cloneclient.domain.rename import RenamePlan
from cloneclient.infrastructure.xapk_inspector import inspect
from cloneclient.shared.constants import OLD_PACKAGE


class InspectService:
    def inspect(self, path: Path, on_log: Callable[[str], None] | None = None) -> ApkInfo:
        if on_log is not None:
            on_log(f"Inspecting {path.name}")
        return inspect(path)

    def warnings(self, info: ApkInfo, plan: RenamePlan | None = None) -> list[str]:
        return _warnings(info, plan)

    def format_report(self, info: ApkInfo, plan: RenamePlan | None = None) -> str:
        lines = [
            f"Source: {info.source}",
            f"Type: {'XAPK split bundle' if info.is_xapk else 'APK'}",
            f"Package: {info.package_name or 'unknown'}",
            f"Version: {info.version_name or 'unknown'} ({info.version_code or 'unknown'})",
            f"Min SDK: {info.min_sdk if info.min_sdk is not None else 'unknown'}",
            f"Target SDK: {info.target_sdk if info.target_sdk is not None else 'unknown'}",
            f"Split entries: {info.split_count}",
            f"ABIs: {', '.join(info.abis) or 'none'}",
            f"Densities: {', '.join(info.densities) or 'none'}",
            f"Languages: {', '.join(info.languages) or 'none'}",
            f"OBB: {'yes' if info.has_obb else 'no'}",
            f"Size: {_format_size(info.total_size)}",
        ]
        if plan is not None:
            lines.extend(
                [
                    f"Rename target: {plan.new_package}",
                    "Rename mode: full (Java classes, manifest, resources, "
                    "native strings, JNI symbols)",
                    f"JNI symbols: {plan.old_jni_prefix} -> {plan.new_jni_prefix}",
                    f"Native prefix: {plan.old_partial} -> {plan.new_partial}",
                ]
            )
        lines.append("Occurrences:")
        lines.extend(_occurrence_lines(info))
        warnings = self.warnings(info, plan)
        if warnings:
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in warnings)
        return "\n".join(lines)


def _occurrence_lines(info: ApkInfo) -> list[str]:
    if not info.occurrences:
        return ["  none"]
    totals: Counter[tuple[str, str, str]] = Counter()
    for occurrence in info.occurrences:
        totals[(occurrence.container, occurrence.path, occurrence.pattern)] += occurrence.count
    lines = [
        f"  {count:4d}  {container}:{path}  {pattern}"
        for (container, path, pattern), count in sorted(totals.items())
    ]
    if len(lines) > 30:
        extra = len(lines) - 30
        lines = lines[:30] + [f"  ... {extra} more"]
    return lines


def _warnings(info: ApkInfo, plan: RenamePlan | None) -> list[str]:
    warnings: list[str] = []
    if info.has_obb:
        warnings.append("OBB data is not embedded in the APK and must remain external.")
    if info.package_name and info.package_name != OLD_PACKAGE:
        warnings.append(
            f"Input package is {info.package_name}, not the default {OLD_PACKAGE}; "
            "the rename plan uses the input package as the source."
        )
    if plan is not None and not plan.native_length_ok:
        warnings.append("New applicationId is longer and cannot be patched into native strings.")
    if plan is not None:
        warnings.append(
            "Existing app data under the old package is not migrated; the new app uses a new "
            "data directory."
        )
    return warnings


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
