"""Run external Java tools with streaming output, cancellation, and a timeout."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from cloneclient.shared.errors import CancelledError, ToolError

logger = logging.getLogger("cloneclient.process")


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    output: str
    duration: float


def run_command(
    args: Sequence[str | Path],
    *,
    cwd: Path | str | None = None,
    timeout: float = 600.0,
    on_line: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> CommandResult:
    command = [str(arg) for arg in args]
    started = time.monotonic()
    deadline = started + timeout
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
    except FileNotFoundError as exc:
        raise ToolError(f"command not found: {command[0]}") from exc

    lines: list[str] = []

    def read_output() -> None:
        assert process.stdout is not None
        for raw in process.stdout:
            line = raw.rstrip()
            lines.append(line)
            if on_line is not None:
                on_line(line)
            logger.debug("%s", line)

    reader = threading.Thread(target=read_output, name="tool-output", daemon=True)
    reader.start()
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                process.kill()
                process.wait()
                reader.join(timeout=2.0)
                raise CancelledError("operation canceled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                reader.join(timeout=2.0)
                raise ToolError(f"command timed out after {timeout:.0f}s: {command[0]}")
            try:
                returncode = process.wait(timeout=min(0.2, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    reader.join()

    return CommandResult(
        args=tuple(command),
        returncode=returncode,
        output="\n".join(lines),
        duration=time.monotonic() - started,
    )


def require_success(result: CommandResult, action: str) -> None:
    if result.returncode == 0:
        return
    tail = "\n".join(result.output.splitlines()[-20:])
    raise ToolError(f"{action} failed with exit code {result.returncode}\n{tail}")
