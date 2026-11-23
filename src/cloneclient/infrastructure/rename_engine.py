"""Apply the full package rename to a decoded APK tree.

Java classes, the manifest, resources, native strings, and JNI exports all move
to the new applicationId. The native prefix is replaced as well because the
game composes class names from it at runtime.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from cloneclient.domain.rename import PatchReport, RenamePlan
from cloneclient.infrastructure.apktool import prepare_decoded_tree
from cloneclient.infrastructure.jni_rename import rename_jni_symbols
from cloneclient.infrastructure.native_patch import Replacement, patch_native_file
from cloneclient.shared.errors import PipelineError, ToolError

TEXT_ASSET_SUFFIXES = {
    ".txt",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".csv",
    ".cfg",
    ".ini",
    ".properties",
    ".lua",
    ".js",
    ".html",
    ".htm",
}
MAX_ASSET_BYTES = 2_000_000


def apply_rename(
    decoded_dir: Path,
    plan: RenamePlan,
    on_log: Callable[[str], None] | None = None,
    server_replacements: tuple[tuple[str, str], ...] = (),
) -> PatchReport:
    report = PatchReport()
    prepare_decoded_tree(decoded_dir, rename_package=plan.new_package)
    manifest = decoded_dir / "AndroidManifest.xml"
    if not manifest.exists():
        raise PipelineError("decoded tree has no AndroidManifest.xml")
    _patch_text(manifest, plan, report, "manifest", "AndroidManifest.xml")
    _patch_smali(decoded_dir, plan, report)
    _patch_resources(decoded_dir, plan, report)
    _patch_native_libraries(decoded_dir, plan, report, server_replacements)
    report.warn(
        "Full rename: Java classes, manifest, resources, native strings, and JNI symbols "
        "now use the new applicationId."
    )
    report.warn(
        "Existing app data under the old package is not migrated; the new app starts with "
        "a new data directory."
    )
    if on_log is not None:
        for line in report.to_lines():
            on_log(line)
    return report


def _patch_text(
    path: Path,
    plan: RenamePlan,
    report: PatchReport,
    area: str,
    label: str,
) -> None:
    text = path.read_text(encoding="utf-8")
    dot_count = text.count(plan.old_package)
    path_count = text.count(plan.old_path)
    if dot_count or path_count:
        text = text.replace(plan.old_package, plan.new_package)
        text = text.replace(plan.old_path, plan.new_path)
        path.write_text(text, encoding="utf-8")
    report.add(label, plan.old_package, dot_count, area)
    report.add(label, plan.old_path, path_count, area)


def _patch_smali(decoded_dir: Path, plan: RenamePlan, report: PatchReport) -> None:
    for smali in sorted(decoded_dir.glob("smali*")):
        old_dir = smali / plan.old_path
        if not old_dir.exists():
            continue
        new_dir = smali / plan.new_path
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        if new_dir.exists():
            shutil.rmtree(new_dir)
        old_dir.rename(new_dir)
        report.add(f"{smali.name}/{plan.old_path}", "directory", 1, "smali")

    total_dot = 0
    total_path = 0
    for path in decoded_dir.glob(f"smali*/{plan.new_path}/**/*.smali"):
        text = path.read_text(encoding="utf-8")
        dot_count = text.count(plan.old_package)
        path_count = text.count(plan.old_path)
        if dot_count or path_count:
            text = text.replace(plan.old_package, plan.new_package)
            text = text.replace(plan.old_path, plan.new_path)
            path.write_text(text, encoding="utf-8")
        total_dot += dot_count
        total_path += path_count
    report.add("smali", plan.old_package, total_dot, "smali")
    report.add("smali", plan.old_path, total_path, "smali")
    report.warn("Smali rewrite is limited to the app package tree; the verifier checks the dex.")


def _patch_resources(decoded_dir: Path, plan: RenamePlan, report: PatchReport) -> None:
    res_dot = 0
    res_path = 0
    res_root = decoded_dir / "res"
    if res_root.exists():
        for path in res_root.rglob("*.xml"):
            text = path.read_text(encoding="utf-8")
            dot_count = text.count(plan.old_package)
            path_count = text.count(plan.old_path)
            if dot_count or path_count:
                text = text.replace(plan.old_package, plan.new_package)
                text = text.replace(plan.old_path, plan.new_path)
                path.write_text(text, encoding="utf-8")
            res_dot += dot_count
            res_path += path_count
    report.add("res", plan.old_package, res_dot, "resource")
    report.add("res", plan.old_path, res_path, "resource")

    asset_dot = 0
    asset_path = 0
    assets_root = decoded_dir / "assets"
    if assets_root.exists():
        for path in assets_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_ASSET_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_ASSET_BYTES:
                    continue
            except OSError:
                continue
            data = path.read_bytes()
            old_dot = plan.old_package.encode("ascii")
            old_path = plan.old_path.encode("ascii")
            dot_count = data.count(old_dot)
            path_count = data.count(old_path)
            if dot_count or path_count:
                data = data.replace(old_dot, plan.new_package.encode("ascii"))
                data = data.replace(old_path, plan.new_path.encode("ascii"))
                path.write_bytes(data)
            asset_dot += dot_count
            asset_path += path_count
    report.add("assets", plan.old_package, asset_dot, "resource")
    report.add("assets", plan.old_path, asset_path, "resource")


def _patch_native_libraries(
    decoded_dir: Path,
    plan: RenamePlan,
    report: PatchReport,
    server_replacements: tuple[tuple[str, str], ...] = (),
) -> None:
    replacements = [
        Replacement("package", plan.old_package, plan.new_package),
        Replacement("path", plan.old_path, plan.new_path),
        Replacement("partial", plan.old_partial, plan.new_partial),
        Replacement(
            "partial_path",
            plan.old_partial.replace(".", "/"),
            plan.new_partial.replace(".", "/"),
        ),
    ]
    for index, (old, new) in enumerate(server_replacements, 1):
        replacements.append(Replacement(f"server{index}", old, new))
    for library in (decoded_dir / "lib").rglob("*.so"):
        relative = str(library.relative_to(decoded_dir))
        try:
            jni_count = rename_jni_symbols(library, plan.old_jni_prefix, plan.new_jni_prefix)
        except ToolError as exc:
            raise PipelineError(str(exc)) from exc
        report.add(relative, plan.old_jni_prefix, jni_count, "jni")
        try:
            counts = patch_native_file(library, replacements)
        except ValueError as exc:
            raise PipelineError(str(exc)) from exc
        for label, count in counts.items():
            report.add(relative, label, count, "native")
