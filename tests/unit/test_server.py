import pytest

from cloneclient.domain.server import (
    SERVER_1,
    SERVER_2,
    SERVER_LENGTH,
    build_server_replacements,
    validate_server,
)


def test_server_hosts_are_same_length() -> None:
    assert SERVER_LENGTH == 18
    assert len(SERVER_1) == len(SERVER_2) == SERVER_LENGTH


def test_valid_server_replacement() -> None:
    assert validate_server("www.example001.com", "Server 1") == "www.example001.com"


def test_empty_server_keeps_original() -> None:
    assert validate_server("", "Server 1") == ""
    assert build_server_replacements("", "") == ()


def test_server_requires_exact_length() -> None:
    with pytest.raises(ValueError, match="exactly 18"):
        validate_server("www.example1.com", "Server 1")
    with pytest.raises(ValueError, match="exactly 18"):
        validate_server("www.example0111.com", "Server 1")


def test_server_rejects_spaces_and_non_ascii() -> None:
    with pytest.raises(ValueError, match="spaces"):
        validate_server("www.exa mple01.com", "Server 1")
    with pytest.raises(ValueError, match="ASCII"):
        validate_server("www.contoh01.com\u00e9x", "Server 1")


def test_build_server_replacements_skips_empty_values() -> None:
    assert build_server_replacements("www.example001.com", "") == (
        (SERVER_1, "www.example001.com"),
    )
    assert build_server_replacements("www.example001.com", "www.example002.com") == (
        (SERVER_1, "www.example001.com"),
        (SERVER_2, "www.example002.com"),
    )
