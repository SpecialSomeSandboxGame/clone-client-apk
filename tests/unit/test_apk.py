import pytest

from cloneclient.domain.apk import (
    ApkInfo,
    classify_split,
    native_patch_fits,
    validate_application_id,
)
from cloneclient.shared.constants import NEW_PACKAGE, OLD_PACKAGE


def test_valid_application_id() -> None:
    assert validate_application_id(NEW_PACKAGE) == NEW_PACKAGE
    assert validate_application_id("com.example.app_2") == "com.example.app_2"


@pytest.mark.parametrize(
    "value",
    ["com.dev-rt.growtopia", "single", "1.com.app", "com..app", "com.app-name"],
)
def test_invalid_application_id(value: str) -> None:
    with pytest.raises(ValueError):
        validate_application_id(value)


def test_native_replacement_rule() -> None:
    assert native_patch_fits(OLD_PACKAGE, NEW_PACKAGE)
    assert not native_patch_fits(OLD_PACKAGE, "com.dev_rt.gtopia")
    assert not native_patch_fits(OLD_PACKAGE, "com.dev.rtsoft.growtopia")


def test_classify_split() -> None:
    assert classify_split("com.rtsoft.growtopia.apk") == ("base", "")
    assert classify_split("config.arm64_v8a.apk") == ("abi", "arm64_v8a")
    assert classify_split("config.xxhdpi.apk") == ("density", "xxhdpi")
    assert classify_split("config.pt.apk") == ("language", "pt")
    assert classify_split("config.unknown.apk") == ("other", "unknown")


def test_apk_info_is_immutable() -> None:
    info = ApkInfo(
        source="app.xapk",
        is_xapk=True,
        package_name=OLD_PACKAGE,
        version_name="5.62",
        version_code="428",
        min_sdk=32,
        target_sdk=37,
        splits=(),
        abis=(),
        densities=(),
        languages=(),
        has_obb=False,
        total_size=10,
        occurrences=(),
    )

    assert info.split_count == 0
    with pytest.raises(AttributeError):
        info.package_name = "changed"  # type: ignore[misc]
