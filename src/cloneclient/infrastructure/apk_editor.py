"""Adapter for merging split APKs with APKEditor."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from cloneclient.infrastructure.process_runner import require_success, run_command
from cloneclient.infrastructure.toolchain import Toolchain
from cloneclient.shared.errors import ToolError


def merge(
    input_path: Path,
    output_path: Path,
    toolchain: Toolchain,
    on_line: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            toolchain.java,
            "-jar",
            toolchain.apkeditor_jar,
            "m",
            "-i",
            input_path,
            "-o",
            output_path,
            "-f",
        ],
        timeout=900,
        on_line=on_line,
        cancel_event=cancel_event,
    )
    require_success(result, "APKEditor merge")
    if not output_path.exists():
        raise ToolError("APKEditor did not produce a merged APK")
    return output_path
