"""Validate native server endpoint replacements for libgrowtopia.so."""

from __future__ import annotations

SERVER_1 = "www.growtopia1.com"
SERVER_2 = "www.growtopia2.com"
SERVER_LENGTH = len(SERVER_1)


def validate_server(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if len(value) != SERVER_LENGTH:
        raise ValueError(f"{label} must be exactly {SERVER_LENGTH} characters")
    if not value.isascii():
        raise ValueError(f"{label} must contain only ASCII characters")
    if any(character.isspace() for character in value):
        raise ValueError(f"{label} cannot contain spaces")
    return value


def build_server_replacements(
    server1: str,
    server2: str,
) -> tuple[tuple[str, str], ...]:
    first = validate_server(server1, "Server 1")
    second = validate_server(server2, "Server 2")
    replacements: list[tuple[str, str]] = []
    if first:
        replacements.append((SERVER_1, first))
    if second:
        replacements.append((SERVER_2, second))
    return tuple(replacements)
