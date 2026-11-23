"""Rename exported JNI symbols in an ELF shared library.

A Java package rename also changes every JNI symbol the runtime looks up. The
dynamic linker resolves those names through the ELF hash tables, so an in-place
string replacement is not enough: the hash entries would still describe the
old names. LIEF rebuilds the dynamic symbol table and the hash sections when
the binary is written.
"""

from __future__ import annotations

from pathlib import Path

import lief

from cloneclient.shared.errors import ToolError


def rename_jni_symbols(path: Path, old_prefix: str, new_prefix: str) -> int:
    try:
        binary = lief.ELF.parse(str(path))
    except Exception as exc:
        raise ToolError(f"cannot parse native library {path}: {exc}") from exc
    if binary is None:
        raise ToolError(f"cannot parse native library {path}")
    count = 0
    for symbol in binary.dynamic_symbols:
        if symbol.name.startswith(old_prefix):
            symbol.name = new_prefix + symbol.name[len(old_prefix) :]
            count += 1
    if count:
        temporary = path.with_suffix(f"{path.suffix}.lief")
        try:
            binary.write(str(temporary))
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise ToolError(f"cannot write native library {path}: {exc}") from exc
    return count
