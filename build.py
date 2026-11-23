"""Build a standalone Windows executable with PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "build" / "app.spec"
FETCH_TOOLS = ROOT / "scripts" / "fetch_tools.py"
FETCH_JDK = ROOT / "scripts" / "fetch_jdk.py"


def ensure_tools() -> int:
    # The script verifies pinned hashes, so an interrupted or replaced JAR is
    # detected before PyInstaller bundles it into the executable.
    return subprocess.call([sys.executable, str(FETCH_TOOLS)], cwd=ROOT)


def ensure_runtime() -> int:
    # The packaged executable must run without a host JDK. The runtime is built
    # from a pinned Temurin release and bundled as data.
    return subprocess.call([sys.executable, str(FETCH_JDK)], cwd=ROOT)


def main() -> int:
    if sys.platform != "win32":
        print("Building the executable is supported on Windows only.")
        return 1
    if ensure_tools() != 0:
        print("Tool JAR download failed.")
        return 1
    if ensure_runtime() != 0:
        print("Bundled Java runtime build failed.")
        return 1
    runtime_java = ROOT / "runtime" / "bin" / ("java.exe" if sys.platform == "win32" else "java")
    if not runtime_java.is_file():
        print("Bundled Java runtime is missing.")
        return 1
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build" / "_work"),
        str(SPEC),
    ]
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
