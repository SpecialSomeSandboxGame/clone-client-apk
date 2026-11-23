"""Build the bundled Java runtime from a pinned Temurin JDK."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

JDK_RELEASE = "jdk-21.0.13.1+2"
JDK_URL = (
    "https://github.com/adoptium/temurin21-binaries/releases/download/"
    "jdk-21.0.13.1%2B2/OpenJDK21U-jdk_x64_windows_hotspot_21.0.13.1_2.zip"
)
JDK_SHA256 = "bbebea1469996b276683c9299c227b294f85c847039c82633218186a4ad4fbf2"
JDK_SIZE = 205447663
RUNTIME_MODULES = "java.base,java.desktop,java.logging"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_jdk(destination: Path) -> None:
    if destination.exists() and sha256(destination) == JDK_SHA256:
        print(f"verified {destination.name}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    print(f"downloading {JDK_RELEASE}")
    request = urllib.request.Request(JDK_URL, headers={"User-Agent": "cloneclient-runtime"})
    with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    size = partial.stat().st_size
    digest = sha256(partial)
    if size != JDK_SIZE or digest != JDK_SHA256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"JDK verification failed: size {size}, sha256 {digest}")
    partial.replace(destination)
    print(f"installed {destination.name}")


def extract_jdk(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(destination)
    for candidate in destination.iterdir():
        jlink = candidate / "bin" / "jlink.exe"
        if candidate.is_dir() and jlink.is_file():
            return jlink
    raise RuntimeError("jlink.exe was not found in the JDK archive")


def build_runtime(jlink: Path, runtime: Path) -> None:
    if runtime.is_dir():
        shutil.rmtree(runtime)
    elif runtime.exists():
        runtime.unlink()
    result = subprocess.run(
        [
            str(jlink),
            "--add-modules",
            RUNTIME_MODULES,
            "--output",
            str(runtime),
            "--strip-debug",
            "--no-header-files",
            "--no-man-pages",
            "--compress=2",
        ],
        check=False,
    )
    if result.returncode != 0:
        shutil.rmtree(runtime, ignore_errors=True)
        raise RuntimeError("jlink failed to build the runtime")


def ensure_runtime(root: Path) -> None:
    runtime = root / "runtime"
    java = runtime / "bin" / "java.exe"
    keytool = runtime / "bin" / "keytool.exe"
    stale = runtime.with_name("runtime.tmp")
    if stale.is_dir():
        shutil.rmtree(stale, ignore_errors=True)
    elif stale.exists():
        stale.unlink()
    if java.is_file() and keytool.is_file():
        print("runtime already present")
        return

    cache = root / ".cache" / "jdk"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f"{JDK_RELEASE}.zip"
    download_jdk(archive)
    extracted = cache / "extracted"
    if extracted.exists():
        shutil.rmtree(extracted)
    jlink = extract_jdk(archive, extracted)
    print("building minimal runtime")
    build_runtime(jlink, runtime)
    if not java.is_file() or not keytool.is_file():
        raise RuntimeError("the built runtime is missing java.exe or keytool.exe")
    print(f"runtime ready: {runtime}")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    try:
        ensure_runtime(root)
    except Exception as exc:
        print(f"runtime build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
