"""Locate Java and the pinned JAR tools used by the repackager."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from cloneclient.infrastructure.process_runner import run_command
from cloneclient.shared.errors import ToolError


def bundled_tools_dir() -> Path:
    # PyInstaller onefile extracts data under _MEIPASS. Source runs keep the
    # tools directory beside the project root so the same code path is tested.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "tools"
    # __file__ is already absolute here. Resolving it follows junctions and is
    # noticeably slow on Windows installations with redirected profile paths.
    return Path(__file__).parents[3] / "tools"


def _bundled_java() -> Path | None:
    # Prefer the pinned runtime so the packaged app does not depend on a host
    # JDK. Source runs use the same runtime when the build has created it.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parents[3]
    candidate = base / "runtime" / "bin" / ("java.exe" if sys.platform == "win32" else "java")
    return candidate if candidate.is_file() else None


def _find_java() -> Path:
    bundled = _bundled_java()
    if bundled is not None:
        return bundled
    # Avoid shutil.which here. It walks every PATH entry and can block for a
    # long time when a disconnected network drive is on PATH. Known JDK
    # locations plus JAVA_HOME cover normal Windows installs without that risk.
    candidates: list[Path] = []
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidates.append(
            Path(java_home) / "bin" / ("java.exe" if sys.platform == "win32" else "java")
        )
    if sys.platform == "win32":
        candidates.append(Path("C:/Program Files/Common Files/Oracle/Java/javapath/java.exe"))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    if sys.platform == "win32":
        for root in (
            Path("C:/Program Files/Java"),
            Path("C:/Program Files/Eclipse Adoptium"),
            Path("C:/Program Files/Microsoft"),
        ):
            try:
                entries = sorted(os.scandir(root), key=lambda entry: entry.name, reverse=True)
            except OSError:
                continue
            for entry in entries:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                candidate = Path(entry.path) / "bin" / "java.exe"
                if candidate.is_file():
                    return candidate
    raise ToolError("Java 17 or newer was not found. Install a JDK and set JAVA_HOME.")


def _java_home(java: Path) -> Path | None:
    try:
        result = run_command([java, "-XshowSettings:properties", "-version"], timeout=30)
    except ToolError:
        return None
    match = re.search(r"^\s*java\.home = (.+)$", result.output, re.MULTILINE)
    return Path(match.group(1).strip()) if match else None


def _find_keytool(java: Path) -> Path:
    sibling = java.with_name("keytool.exe" if sys.platform == "win32" else "keytool")
    if sibling.is_file():
        return sibling
    if sys.platform == "win32":
        for root in (
            Path("C:/Program Files/Java"),
            Path("C:/Program Files/Eclipse Adoptium"),
            Path("C:/Program Files/Microsoft"),
        ):
            try:
                entries = sorted(os.scandir(root), key=lambda entry: entry.name, reverse=True)
            except OSError:
                continue
            for entry in entries:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                candidate = Path(entry.path) / "bin" / "keytool.exe"
                if candidate.is_file():
                    return candidate
    home = _java_home(java)
    if home is not None:
        candidate = home / "bin" / ("keytool.exe" if sys.platform == "win32" else "keytool")
        if candidate.is_file():
            return candidate
    raise ToolError("keytool was not found. Install a full JDK, not only a JRE.")


@lru_cache(maxsize=4)
def _read_java_version(java: Path) -> str:
    # Starting java.exe is slow on machines with aggressive antivirus. Cache it
    # so the preflight check and the repack worker do not each pay that cost.
    result = run_command([java, "-version"], timeout=30)
    # java -version writes to stderr, which run_command merges into output.
    match = re.search(r'version "([^"]+)"', result.output)
    return match.group(1) if match else result.output.strip()


@dataclass(frozen=True)
class Toolchain:
    java: Path
    keytool: Path
    apkeditor_jar: Path
    apktool_jar: Path
    signer_jar: Path

    @classmethod
    def discover(cls, tools_dir: Path | None = None) -> Toolchain:
        java = _find_java()
        keytool = _find_keytool(java)
        base = tools_dir if tools_dir is not None else bundled_tools_dir()
        apkeditor = base / "APKEditor.jar"
        apktool = base / "apktool.jar"
        signer = base / "uber-apk-signer.jar"
        missing = [path for path in (apkeditor, apktool, signer) if not path.exists()]
        if missing:
            names = ", ".join(str(path) for path in missing)
            raise ToolError(f"missing tool JAR(s): {names}. Run scripts/fetch_tools.py.")
        return cls(
            java=java,
            keytool=keytool,
            apkeditor_jar=apkeditor,
            apktool_jar=apktool,
            signer_jar=signer,
        )

    def java_version(self) -> str:
        return _read_java_version(self.java)

    def require_java_17(self) -> None:
        version = self.java_version()
        try:
            major = int(version.split(".")[0])
        except (ValueError, IndexError) as exc:
            raise ToolError(f"could not parse Java version: {version}") from exc
        if major < 17:
            raise ToolError(f"Java 17 or newer is required, found {version}")
