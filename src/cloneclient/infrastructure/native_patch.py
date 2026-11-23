"""In-place replacement for package strings in native libraries.

The replacement keeps the exact byte length so ELF offsets and every following
string stay valid. JNI symbol names are renamed separately by the LIEF adapter;
changing them with plain bytes would leave the GNU hash stale and dlsym would
miss the new names.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Replacement:
    label: str
    old: str
    new: str


def replace_patterns(
    data: bytes,
    replacements: Sequence[Replacement],
) -> tuple[bytes, dict[str, int]]:
    output = data
    counts: dict[str, int] = {}
    for replacement in replacements:
        old = replacement.old.encode("ascii")
        new = replacement.new.encode("ascii")
        if len(new) != len(old):
            raise ValueError(f"{replacement.label} replacement must keep the original length")
        counts[replacement.label] = output.count(old)
        if counts[replacement.label]:
            output = output.replace(old, new)
    return output, counts


def patch_native_file(path: Path, replacements: Sequence[Replacement]) -> dict[str, int]:
    data = path.read_bytes()
    patched, counts = replace_patterns(data, replacements)
    if any(counts.values()):
        path.write_bytes(patched)
    return counts
