from cloneclient.domain.settings import Settings, WindowGeometry
from cloneclient.shared.constants import DEFAULT_KEYSTORE_ALIAS


def test_settings_round_trip() -> None:
    settings = Settings(WindowGeometry(10, 20, 800, 600))

    assert Settings.from_dict(settings.to_dict()) == settings


def test_settings_round_trip_theme() -> None:
    settings = Settings(theme="dark")

    assert Settings.from_dict(settings.to_dict()) == settings


def test_settings_ignores_malformed_payload() -> None:
    assert Settings.from_dict({"window_geometry": {"x": "bad"}}) == Settings()
    assert Settings.from_dict("not a mapping") == Settings()


def test_settings_rejects_unusable_geometry() -> None:
    settings = Settings(WindowGeometry(0, 0, 100, 100))

    assert Settings.from_dict(settings.to_dict()) == Settings()


def test_settings_defaults_unknown_theme() -> None:
    assert Settings.from_dict({"theme": "neon"}).theme == "light"


def test_settings_round_trip_repack_fields() -> None:
    settings = Settings(
        repack_output_dir="D:/output",
        keystore_path="D:/keys/release.jks",
        keystore_alias="release",
    )

    assert Settings.from_dict(settings.to_dict()) == settings


def test_settings_normalizes_empty_repack_fields() -> None:
    settings = Settings.from_dict(
        {"repack_output_dir": "  ", "keystore_path": "", "keystore_alias": ""}
    )

    assert settings.repack_output_dir is None
    assert settings.keystore_path is None
    assert settings.keystore_alias == DEFAULT_KEYSTORE_ALIAS
