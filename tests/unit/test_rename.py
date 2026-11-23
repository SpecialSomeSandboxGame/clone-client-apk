import pytest

from cloneclient.domain.rename import PatchReport, build_rename_plan, jni_prefix, partial_prefix
from cloneclient.shared.constants import NEW_PACKAGE, OLD_PACKAGE


def test_build_rename_plan_moves_package_identity() -> None:
    plan = build_rename_plan(NEW_PACKAGE)

    assert plan.old_package == OLD_PACKAGE
    assert plan.new_package == NEW_PACKAGE
    assert plan.old_path == "com/rtsoft/growtopia"
    assert plan.new_path == "com/dev_rt/growtopia"
    assert plan.old_jni_prefix == "Java_com_rtsoft_growtopia_"
    assert plan.new_jni_prefix == "Java_com_dev_1rt_growtopia_"
    assert plan.old_partial == "com.rtsoft."
    assert plan.new_partial == "com.dev_rt."
    assert plan.native_length_ok is True


def test_jni_prefix_encodes_underscore() -> None:
    assert jni_prefix("com.dev_rt.growtopia") == "Java_com_dev_1rt_growtopia_"
    assert partial_prefix("com.dev_rt.growtopia") == "com.dev_rt."


def test_build_rename_plan_rejects_longer_native_string() -> None:
    with pytest.raises(ValueError, match="exactly 20"):
        build_rename_plan("com.dev.rtsoft.growtopia")


def test_build_rename_plan_rejects_shorter_native_string() -> None:
    with pytest.raises(ValueError, match="exactly 20"):
        build_rename_plan("com.devrt.growtopia")


def test_build_rename_plan_rejects_prefix_length_change() -> None:
    with pytest.raises(ValueError, match="prefix stays 11"):
        build_rename_plan("com.devrtsoft.gtopia")


def test_patch_report_aggregates() -> None:
    report = PatchReport()
    report.add("AndroidManifest.xml", OLD_PACKAGE, 4, "manifest")
    report.add("libgrowtopia.so", OLD_PACKAGE, 1, "native")
    report.add("unused", OLD_PACKAGE, 0, "native")
    report.warn("full rename")

    assert report.total == 5
    assert len(report.entries) == 2
    assert any("warning:" in line for line in report.to_lines())
