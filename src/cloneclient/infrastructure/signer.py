"""Sign and verify APKs with uber-apk-signer."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from cloneclient.infrastructure.process_runner import require_success, run_command
from cloneclient.infrastructure.toolchain import Toolchain
from cloneclient.shared.errors import ToolError


def sign(
    apk_path: Path,
    keystore: Path,
    password: str,
    alias: str,
    output_dir: Path,
    toolchain: Toolchain,
    on_line: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*-signed.apk"):
        stale.unlink()
    for stale in output_dir.glob("*.idsig"):
        stale.unlink()
    result = run_command(
        [
            toolchain.java,
            "-jar",
            toolchain.signer_jar,
            "--apks",
            apk_path,
            "--ks",
            keystore,
            "--ksAlias",
            alias,
            "--ksPass",
            password,
            "--ksKeyPass",
            password,
            "-o",
            output_dir,
            "--verbose",
        ],
        timeout=900,
        on_line=on_line,
        cancel_event=cancel_event,
    )
    require_success(result, "APK signing")
    candidates = sorted(output_dir.glob("*-signed.apk"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise ToolError("signer did not produce a signed APK")
    return candidates[-1]


def verify(
    apk_path: Path,
    toolchain: Toolchain,
    on_line: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> tuple[bool, str]:
    result = run_command(
        [
            toolchain.java,
            "-jar",
            toolchain.signer_jar,
            "--apks",
            apk_path,
            "--onlyVerify",
            "--verbose",
        ],
        timeout=300,
        on_line=on_line,
        cancel_event=cancel_event,
    )
    output = result.output
    lowered = output.lower()
    ok = (
        result.returncode == 0
        and "signature verified" in lowered
        and "zipalign verified" in lowered
    )
    return ok, output
