import sys
from pathlib import Path

from cloneclient.infrastructure import toolchain


def _runtime_bin(tmp_path: Path) -> Path:
    binary = tmp_path / "runtime" / "bin"
    binary.mkdir(parents=True)
    return binary


def test_bundled_runtime_is_preferred(tmp_path: Path, monkeypatch) -> None:
    java_name = "java.exe" if sys.platform == "win32" else "java"
    java = _runtime_bin(tmp_path) / java_name
    java.write_bytes(b"")
    monkeypatch.setattr(toolchain.sys, "frozen", True, raising=False)
    monkeypatch.setattr(toolchain.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert toolchain._find_java() == java


def test_bundled_runtime_uses_sibling_keytool(tmp_path: Path) -> None:
    java_name = "java.exe" if sys.platform == "win32" else "java"
    keytool_name = "keytool.exe" if sys.platform == "win32" else "keytool"
    binary = _runtime_bin(tmp_path)
    java = binary / java_name
    keytool = binary / keytool_name
    java.write_bytes(b"")
    keytool.write_bytes(b"")

    assert toolchain._find_keytool(java) == keytool
