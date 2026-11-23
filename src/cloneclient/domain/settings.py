"""Pure settings model and JSON-friendly serialization."""

from __future__ import annotations

from dataclasses import dataclass

from cloneclient.shared.constants import DEFAULT_KEYSTORE_ALIAS

MIN_WIDTH = 320
MIN_HEIGHT = 240
DEFAULT_THEME = "light"
THEMES = ("light", "dark")


@dataclass(frozen=True)
class WindowGeometry:
    x: int
    y: int
    width: int
    height: int

    def is_usable(self) -> bool:
        return self.width >= MIN_WIDTH and self.height >= MIN_HEIGHT


@dataclass(frozen=True)
class Settings:
    window_geometry: WindowGeometry | None = None
    theme: str = DEFAULT_THEME
    repack_output_dir: str | None = None
    keystore_path: str | None = None
    keystore_alias: str = DEFAULT_KEYSTORE_ALIAS

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"theme": self.theme, "keystore_alias": self.keystore_alias}
        if self.repack_output_dir:
            data["repack_output_dir"] = self.repack_output_dir
        if self.keystore_path:
            data["keystore_path"] = self.keystore_path
        if self.window_geometry is None:
            return data
        geometry = self.window_geometry
        data["window_geometry"] = {
            "x": geometry.x,
            "y": geometry.y,
            "width": geometry.width,
            "height": geometry.height,
        }
        return data

    @classmethod
    def from_dict(cls, data: object) -> Settings:
        if not isinstance(data, dict):
            return cls()
        theme = data.get("theme")
        if theme not in THEMES:
            theme = DEFAULT_THEME
        output_dir = _optional_text(data.get("repack_output_dir"))
        keystore_path = _optional_text(data.get("keystore_path"))
        alias = _optional_text(data.get("keystore_alias")) or DEFAULT_KEYSTORE_ALIAS
        raw = data.get("window_geometry")
        if not isinstance(raw, dict):
            return cls(
                theme=theme,
                repack_output_dir=output_dir,
                keystore_path=keystore_path,
                keystore_alias=alias,
            )
        try:
            geometry = WindowGeometry(
                x=int(raw["x"]),
                y=int(raw["y"]),
                width=int(raw["width"]),
                height=int(raw["height"]),
            )
        except (KeyError, TypeError, ValueError):
            return cls(
                theme=theme,
                repack_output_dir=output_dir,
                keystore_path=keystore_path,
                keystore_alias=alias,
            )
        # A saved geometry can be stale after a monitor change, so reject
        # values that cannot produce a usable window.
        if not geometry.is_usable():
            return cls(
                theme=theme,
                repack_output_dir=output_dir,
                keystore_path=keystore_path,
                keystore_alias=alias,
            )
        return cls(
            window_geometry=geometry,
            theme=theme,
            repack_output_dir=output_dir,
            keystore_path=keystore_path,
            keystore_alias=alias,
        )


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
