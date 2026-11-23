"""Command line entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from cloneclient.bootstrap import run


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    inspect_path = None
    if "--inspect" in args:
        index = args.index("--inspect")
        if index + 1 >= len(args):
            print("--inspect requires a path", file=sys.stderr)
            return 2
        inspect_path = Path(args[index + 1])
    return run(
        smoke="--smoke" in args,
        crash_test="--crash-test" in args,
        tool_check="--tool-check" in args,
        inspect_path=inspect_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
