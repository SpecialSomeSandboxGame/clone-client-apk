"""Download and verify the pinned Java tools used by the repackager."""

from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

TOOLS = {
    "APKEditor.jar": {
        "url": "https://github.com/REAndroid/APKEditor/releases/download/V1.4.9/APKEditor-1.4.9.jar",
        "sha256": "a9cd40df818845456be6d696de6110c89edf4b0a0580cb83438ed6b25a366e67",
    },
    "apktool.jar": {
        "url": "https://github.com/iBotPeaches/Apktool/releases/download/v3.0.3/apktool_3.0.3.jar",
        "sha256": "dbf930b076c6b9be08d57c449cacefc3bdd6b71ebd59b3066fc0e1f5b14f9423",
    },
    "uber-apk-signer.jar": {
        "url": "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar",
        "sha256": "e1299fd6fcf4da527dd53735b56127e8ea922a321128123b9c32d619bba1d835",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_tools(tools_dir: Path) -> None:
    tools_dir.mkdir(parents=True, exist_ok=True)
    for name, spec in TOOLS.items():
        destination = tools_dir / name
        if destination.exists() and sha256(destination) == spec["sha256"]:
            print(f"verified {name}")
            continue
        print(f"downloading {name}")
        partial = destination.with_suffix(destination.suffix + ".part")
        request = urllib.request.Request(spec["url"], headers={"User-Agent": "cloneclient-tools"})
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        actual = sha256(partial)
        if actual != spec["sha256"]:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"hash mismatch for {name}: {actual}")
        partial.replace(destination)
        print(f"installed {name}")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    try:
        ensure_tools(root / "tools")
    except Exception as exc:
        print(f"tool download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
