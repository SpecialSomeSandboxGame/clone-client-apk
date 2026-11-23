"""Fail when project source or docs contain emoji or the em dash character."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

EM_DASH = "\u2014"
SCAN_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".txt", ".spec", ".json"}
SKIP_DIRS = {
    ".git",
    ".venv",
    ".uv",
    "build",
    "dist",
    "__pycache__",
    "node_modules",
    ".commandcode",
    ".opencode",
    ".mandor",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
# Emoji ranges cover the pictographic blocks used in UI text.
EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),
    (0x2600, 0x27BF),
    (0xFE00, 0xFE0F),
)


def is_emoji(char: str) -> bool:
    code = ord(char)
    return any(start <= code <= end for start, end in EMOJI_RANGES)


def scan_file(path: Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), start=1):
        if EM_DASH in line:
            problems.append(f"{path}:{number}: em dash U+2014")
        if any(is_emoji(char) for char in line):
            problems.append(f"{path}:{number}: emoji")
    return problems


def iter_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    problems: list[str] = []
    for path in iter_files(root):
        problems.extend(scan_file(path))
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} style problem(s) found")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
