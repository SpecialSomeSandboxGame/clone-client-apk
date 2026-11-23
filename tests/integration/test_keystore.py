from pathlib import Path

import pytest

from cloneclient.infrastructure.keystore import ensure_keystore
from cloneclient.infrastructure.toolchain import Toolchain
from cloneclient.shared.errors import InputError, ToolError


def _toolchain() -> Toolchain:
    try:
        return Toolchain.discover()
    except ToolError as exc:
        pytest.skip(str(exc))


def test_generate_and_validate_keystore(tmp_path: Path) -> None:
    toolchain = _toolchain()
    path = tmp_path / "release.jks"

    ensure_keystore(path, "testpass", "test", toolchain)
    assert path.exists()
    ensure_keystore(path, "testpass", "test", toolchain)

    with pytest.raises(InputError):
        ensure_keystore(path, "wrongpass", "test", toolchain)
