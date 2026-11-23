"""Pure diagnostics formatting with no GUI or platform dependencies."""

from __future__ import annotations

from collections.abc import Mapping


def build_diagnostics(values: Mapping[str, str]) -> str:
    """Render an ordered mapping as stable key: value lines.

    Callers pass an ordered mapping so copied reports stay comparable across
    runs and can be attached to bug reports without extra cleanup.
    """
    return "\n".join(f"{key}: {value}" for key, value in values.items())
