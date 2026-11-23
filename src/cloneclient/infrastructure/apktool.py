"""Adapter for apktool decode and rebuild operations."""

from __future__ import annotations

import re
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

from cloneclient.infrastructure.process_runner import require_success, run_command
from cloneclient.infrastructure.toolchain import Toolchain
from cloneclient.shared.errors import ToolError

UNCOMPRESSED_ENTRIES = ("AndroidManifest.xml", "arsc", "so")


def decode(
    apk_path: Path,
    output_dir: Path,
    toolchain: Toolchain,
    on_line: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    result = run_command(
        [
            toolchain.java,
            "-jar",
            toolchain.apktool_jar,
            "d",
            apk_path,
            "-o",
            output_dir,
            "-f",
        ],
        timeout=1200,
        on_line=on_line,
        cancel_event=cancel_event,
    )
    require_success(result, "apktool decode")
    return output_dir


def build(
    decoded_dir: Path,
    output_apk: Path,
    toolchain: Toolchain,
    on_line: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    output_apk.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            toolchain.java,
            "-jar",
            toolchain.apktool_jar,
            "b",
            decoded_dir,
            "-o",
            output_apk,
        ],
        timeout=1200,
        on_line=on_line,
        cancel_event=cancel_event,
    )
    require_success(result, "apktool build")
    if not output_apk.exists():
        raise ToolError("apktool did not produce an APK")
    return output_apk


def prepare_decoded_tree(decoded_dir: Path, rename_package: str | None = None) -> None:
    """Force Android 11+ entries to stay uncompressed and set the package name.

    apktool compresses AndroidManifest.xml by default on this toolchain. The
    package manager reads that entry before installing, so it must be stored
    uncompressed and aligned later by the signer. aapt also uses
    renameManifestPackage to rewrite the package name inside resources.arsc.
    """
    yml = decoded_dir / "apktool.yml"
    if not yml.exists():
        raise ToolError("decoded tree has no apktool.yml")
    text = yml.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^renameManifestPackage:.*\n?", "", text)
    if rename_package:
        text = f"renameManifestPackage: {rename_package}\n{text}"
    match = re.search(r"(?m)^doNotCompress:\s*$", text)
    if match is None:
        text = (
            text.rstrip()
            + "\ndoNotCompress:\n"
            + "\n".join(f"- {entry}" for entry in UNCOMPRESSED_ENTRIES)
        )
        yml.write_text(text + "\n", encoding="utf-8")
        return

    start = match.end()
    existing: set[str] = set()
    for line in text[start:].splitlines()[1:]:
        if not line.startswith("- "):
            break
        existing.add(line[2:].strip())
    missing = [entry for entry in UNCOMPRESSED_ENTRIES if entry not in existing]
    if missing:
        insertion = "".join(f"\n- {entry}" for entry in missing)
        text = text[:start] + insertion + text[start:]
    yml.write_text(text, encoding="utf-8")
