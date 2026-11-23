import pytest

from cloneclient.infrastructure.keystore import validate_key_password
from cloneclient.shared.constants import KEY_PASSWORD_MIN_MESSAGE
from cloneclient.shared.errors import InputError


def test_short_password_is_rejected() -> None:
    with pytest.raises(InputError, match="at least 6"):
        validate_key_password("12345")


def test_minimum_length_password_is_accepted() -> None:
    validate_key_password("123456")


def test_message_matches_keytool_wording() -> None:
    with pytest.raises(InputError) as error:
        validate_key_password("")
    assert str(error.value) == KEY_PASSWORD_MIN_MESSAGE
