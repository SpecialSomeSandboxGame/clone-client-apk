"""Repack an XAPK or APK into a signed standalone APK."""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cloneclient.domain.apk import ApkInfo
from cloneclient.domain.rename import PatchReport, build_rename_plan
from cloneclient.domain.server import build_server_replacements
from cloneclient.domain.verification import VerificationReport
from cloneclient.infrastructure import apk_editor, apktool, appearance, keystore, signer
from cloneclient.infrastructure.apk_verifier import verify_apk
from cloneclient.infrastructure.rename_engine import apply_rename
from cloneclient.infrastructure.toolchain import Toolchain
from cloneclient.infrastructure.xapk_inspector import inspect
from cloneclient.shared.constants import (
    DEFAULT_KEYSTORE_ALIAS,
    NEW_PACKAGE,
    OLD_PACKAGE,
)
from cloneclient.shared.errors import CancelledError, InputError, PipelineError

logger = logging.getLogger("cloneclient.repack")

Progress = Callable[[int, str], None]
LogLine = Callable[[str], None]


@dataclass(frozen=True)
class RepackRequest:
    input_path: Path
    output_dir: Path
    new_package: str = NEW_PACKAGE
    app_name: str = ""
    icon_path: Path | None = None
    server1: str = ""
    server2: str = ""
    keystore_path: Path | None = None
    keystore_password: str = ""
    keystore_alias: str = DEFAULT_KEYSTORE_ALIAS


@dataclass(frozen=True)
class RepackResult:
    output_apk: Path
    info: ApkInfo
    patches: PatchReport
    verification: VerificationReport


class RepackService:
    def __init__(self, toolchain: Toolchain | None = None, tools_dir: Path | None = None) -> None:
        self._toolchain = toolchain
        self._tools_dir = tools_dir

    def check_tools(self) -> str:
        toolchain = self._toolchain or Toolchain.discover(self._tools_dir)
        self._toolchain = toolchain
        toolchain.require_java_17()
        return f"Java {toolchain.java_version()}; bundled tools ready"

    def repack(
        self,
        request: RepackRequest,
        on_progress: Progress | None = None,
        on_log: LogLine | None = None,
        cancel_event: threading.Event | None = None,
    ) -> RepackResult:
        source = request.input_path
        if not source.exists():
            raise InputError(f"input file does not exist: {source}")
        if source.suffix.lower() not in {".apk", ".xapk"}:
            raise InputError("select an .xapk or .apk file")
        keystore.validate_key_password(request.keystore_password)

        info = inspect(source)
        old_package = info.package_name or OLD_PACKAGE
        plan = build_rename_plan(request.new_package, old_package=old_package)
        app_name = appearance.validate_app_name(request.app_name)
        if request.icon_path is not None:
            appearance.validate_icon(request.icon_path)
        try:
            server_pairs = build_server_replacements(request.server1, request.server2)
        except ValueError as exc:
            raise InputError(str(exc)) from exc
        toolchain = self._toolchain or Toolchain.discover(self._tools_dir)
        self._toolchain = toolchain
        toolchain.require_java_17()
        request.output_dir.mkdir(parents=True, exist_ok=True)

        work_dir = Path(tempfile.mkdtemp(prefix="cloneclient-repack-"))
        completed = False
        canceled = False
        try:
            self._check_cancel(cancel_event)
            self._stage(5, "Reading input", on_progress, on_log)
            merged = work_dir / "merged.apk"
            if info.is_xapk:
                self._stage(12, "Merging split APKs", on_progress, on_log)
                apk_editor.merge(
                    source,
                    merged,
                    toolchain,
                    on_log,
                    cancel_event=cancel_event,
                )
            else:
                shutil.copy2(source, merged)
            self._check_cancel(cancel_event)

            self._stage(30, "Decoding APK", on_progress, on_log)
            decoded = work_dir / "decoded"
            apktool.decode(merged, decoded, toolchain, on_log, cancel_event=cancel_event)
            # The merged APK and decoded tree are the largest intermediates.
            # Removing each one as soon as its stage finishes keeps the peak
            # disk use within the free space of a typical operator machine.
            merged.unlink(missing_ok=True)
            self._check_cancel(cancel_event)

            self._stage(50, "Renaming package", on_progress, on_log)
            patches = apply_rename(decoded, plan, on_log, server_pairs)
            self._check_cancel(cancel_event)

            if app_name or request.icon_path is not None:
                self._stage(60, "Applying app name and icon", on_progress, on_log)
                appearance.apply_appearance(decoded, app_name, request.icon_path, patches)
                self._check_cancel(cancel_event)

            self._stage(72, "Rebuilding APK", on_progress, on_log)
            unsigned = work_dir / "unsigned.apk"
            apktool.build(decoded, unsigned, toolchain, on_log, cancel_event=cancel_event)
            shutil.rmtree(decoded, ignore_errors=True)
            self._check_cancel(cancel_event)

            self._stage(82, "Preparing keystore", on_progress, on_log)
            keystore_path = request.keystore_path or keystore.default_keystore_path()
            keystore.ensure_keystore(
                keystore_path,
                request.keystore_password,
                request.keystore_alias,
                toolchain,
                on_log,
            )
            self._check_cancel(cancel_event)

            self._stage(88, "Signing APK", on_progress, on_log)
            signed_dir = work_dir / "signed"
            signed = signer.sign(
                unsigned,
                keystore_path,
                request.keystore_password,
                request.keystore_alias,
                signed_dir,
                toolchain,
                on_log,
                cancel_event=cancel_event,
            )
            unsigned.unlink(missing_ok=True)
            for aligned in signed_dir.glob("*-aligned.apk"):
                aligned.unlink(missing_ok=True)
            self._check_cancel(cancel_event)

            self._stage(95, "Verifying APK", on_progress, on_log)
            verification = verify_apk(
                signed,
                plan,
                toolchain,
                cancel_event=cancel_event,
                expected_app_name=app_name or None,
                expected_icon=request.icon_path is not None,
                server_replacements=server_pairs,
            )
            if not verification.passed:
                raise PipelineError("\n".join(verification.to_lines()))

            final = _unique_output_path(request.output_dir, source, info.version_name)
            shutil.move(str(signed), final)
            completed = True
            self._stage(100, "Done", on_progress, on_log)
            return RepackResult(
                output_apk=final,
                info=info,
                patches=patches,
                verification=verification,
            )
        except CancelledError:
            canceled = True
            shutil.rmtree(work_dir, ignore_errors=True)
            if on_log is not None:
                on_log("Repack canceled; partial files removed.")
            raise
        finally:
            if completed:
                shutil.rmtree(work_dir, ignore_errors=True)
            elif not canceled:
                logger.info("work directory kept for debugging: %s", work_dir)
                if on_log is not None:
                    on_log(f"Work directory kept for debugging: {work_dir}")

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Repack canceled")

    def _stage(
        self,
        percent: int,
        message: str,
        on_progress: Progress | None,
        on_log: LogLine | None,
    ) -> None:
        logger.info("%s (%d%%)", message, percent)
        if on_progress is not None:
            on_progress(percent, message)
        if on_log is not None:
            on_log(message)


def _unique_output_path(output_dir: Path, source: Path, version: str | None) -> Path:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem)
    label = re.sub(r"[^A-Za-z0-9._-]+", "_", version or "repack")
    base = f"{stem}-{label}-dev"
    candidate = output_dir / f"{base}.apk"
    counter = 2
    while candidate.exists():
        candidate = output_dir / f"{base}-{counter}.apk"
        counter += 1
    return candidate
