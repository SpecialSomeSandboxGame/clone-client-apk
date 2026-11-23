import pytest

from cloneclient.infrastructure.native_patch import Replacement, replace_patterns
from cloneclient.shared.constants import NEW_PACKAGE, OLD_PACKAGE


def full_replacements() -> list[Replacement]:
    return [
        Replacement("package", OLD_PACKAGE, NEW_PACKAGE),
        Replacement("path", "com/rtsoft/growtopia", "com/dev_rt/growtopia"),
        Replacement("partial", "com.rtsoft.", "com.dev_rt."),
        Replacement("partial_path", "com/rtsoft/", "com/dev_rt/"),
    ]


def test_replaces_full_and_partial_package_strings() -> None:
    data = (
        b"\x00"
        + OLD_PACKAGE.encode()
        + b"\x00"
        + b"com.rtsoft.growtopia.Main"
        + b"\x00"
        + b"com.rtsoft."
        + b"\x00"
        + b"com/rtsoft/growtopia/Main"
        + b"\x00"
        + b"Java_com_rtsoft_growtopia_Main"
        + b"\x00"
    )

    patched, counts = replace_patterns(data, full_replacements())

    assert counts["package"] == 2
    assert counts["path"] == 1
    assert counts["partial"] == 1
    assert len(patched) == len(data)
    assert OLD_PACKAGE.encode() not in patched
    assert b"com.rtsoft." not in patched
    assert b"com/rtsoft/growtopia" not in patched
    assert NEW_PACKAGE.encode() in patched
    assert b"com.dev_rt." in patched
    assert b"com/dev_rt/growtopia/Main" in patched
    # JNI symbol names are renamed by LIEF, not by byte replacement.
    assert b"Java_com_rtsoft_growtopia_Main" in patched


def test_shorter_replacement_is_rejected() -> None:
    with pytest.raises(ValueError, match="original length"):
        replace_patterns(
            b"\x00" + OLD_PACKAGE.encode() + b"\x00",
            [Replacement("package", OLD_PACKAGE, "com.dev_rt.gtopia")],
        )


def test_longer_replacement_is_rejected() -> None:
    with pytest.raises(ValueError):
        replace_patterns(
            b"\x00" + OLD_PACKAGE.encode() + b"\x00",
            [Replacement("package", OLD_PACKAGE, "com.dev.rtsoft.growtopia")],
        )
