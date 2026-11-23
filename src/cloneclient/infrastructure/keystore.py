"""Create and validate the release keystore used for distribution."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cloneclient.infrastructure.paths import user_data_dir
from cloneclient.infrastructure.process_runner import require_success, run_command
from cloneclient.infrastructure.toolchain import Toolchain
from cloneclient.shared.constants import (
    DEFAULT_KEYSTORE_FILENAME,
    KEY_PASSWORD_MIN_MESSAGE,
    MIN_KEY_PASSWORD_LENGTH,
)
from cloneclient.shared.errors import InputError, ToolError

KEY_DNAME = "CN=CloneClient, OU=Development, O=CloneClient, L=Unknown, ST=Unknown, C=US"
VALIDITY_DAYS = "10000"


def default_keystore_path() -> Path:
    return user_data_dir() / "keystore" / DEFAULT_KEYSTORE_FILENAME


def validate_key_password(password: str) -> None:
    """Reject passwords keytool would refuse before any process starts."""
    if len(password) < MIN_KEY_PASSWORD_LENGTH:
        raise InputError(KEY_PASSWORD_MIN_MESSAGE)


def ensure_keystore(
    path: Path,
    password: str,
    alias: str,
    toolchain: Toolchain,
    on_line: Callable[[str], None] | None = None,
) -> Path:
    validate_key_password(password)
    if path.exists():
        _validate(path, password, alias, toolchain)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    # keytool has no non-interactive password source that this GUI can feed
    # reliably, so the password stays on the argument list and never in logs.
    result = run_command(
        [
            toolchain.keytool,
            "-genkeypair",
            "-v",
            "-keystore",
            path,
            "-alias",
            alias,
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            VALIDITY_DAYS,
            "-storepass",
            password,
            "-keypass",
            password,
            "-dname",
            KEY_DNAME,
        ],
        timeout=120,
        on_line=on_line,
    )
    require_success(result, "keystore generation")
    if not path.exists():
        raise ToolError("keytool did not create a keystore")
    return path


def _validate(path: Path, password: str, alias: str, toolchain: Toolchain) -> None:
    result = run_command(
        [
            toolchain.keytool,
            "-list",
            "-keystore",
            path,
            "-alias",
            alias,
            "-storepass",
            password,
        ],
        timeout=60,
    )
    if result.returncode != 0:
        tail = "\n".join(result.output.splitlines()[-10:])
        raise InputError(f"keystore password or alias is invalid\n{tail}")
