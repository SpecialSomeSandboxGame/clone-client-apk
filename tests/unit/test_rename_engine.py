from pathlib import Path

from cloneclient.domain.rename import build_rename_plan
from cloneclient.domain.server import SERVER_1, SERVER_2
from cloneclient.infrastructure.rename_engine import apply_rename
from cloneclient.shared.constants import NEW_PACKAGE, OLD_PACKAGE


def make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "decoded"
    root.mkdir()
    (root / "apktool.yml").write_text(
        "version: 3.0.3\ndoNotCompress:\n- arsc\n- so\n", encoding="utf-8"
    )
    (root / "AndroidManifest.xml").write_text(
        f"""<manifest package="{OLD_PACKAGE}">
  <permission android:name="{OLD_PACKAGE}.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"/>
  <uses-permission android:name="{OLD_PACKAGE}.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"/>
  <application>
    <activity android:name="{OLD_PACKAGE}.Main"/>
    <provider android:authorities="{OLD_PACKAGE}.provider"/>
  </application>
</manifest>
""",
        encoding="utf-8",
    )
    smali = root / "smali" / "com" / "rtsoft" / "growtopia"
    smali.mkdir(parents=True)
    (smali / "Main.smali").write_text(
        f'.class public Lcom/rtsoft/growtopia/Main;\nconst-string v0, "{OLD_PACKAGE}.Main"\n',
        encoding="utf-8",
    )
    library = root / "lib" / "arm64-v8a" / "libgrowtopia.so"
    library.parent.mkdir(parents=True)
    library.write_bytes(
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
        + SERVER_1.encode()
        + b"\x00"
        + SERVER_2.encode()
        + b"\x00"
    )
    return root


def test_apply_rename_moves_manifest_smali_and_native_strings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "cloneclient.infrastructure.rename_engine.rename_jni_symbols",
        lambda *args: 0,
    )
    root = make_tree(tmp_path)
    plan = build_rename_plan(NEW_PACKAGE)

    report = apply_rename(root, plan)

    manifest = (root / "AndroidManifest.xml").read_text(encoding="utf-8")
    assert f'package="{NEW_PACKAGE}"' in manifest
    assert f'android:authorities="{NEW_PACKAGE}.provider"' in manifest
    assert f'android:name="{NEW_PACKAGE}.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"' in manifest
    assert f'android:name="{NEW_PACKAGE}.Main"' in manifest
    assert OLD_PACKAGE not in manifest

    new_smali = root / "smali" / "com" / "dev_rt" / "growtopia" / "Main.smali"
    old_smali = root / "smali" / "com" / "rtsoft" / "growtopia" / "Main.smali"
    assert new_smali.exists()
    assert not old_smali.exists()
    body = new_smali.read_text(encoding="utf-8")
    assert "Lcom/dev_rt/growtopia/Main;" in body
    assert f'"{NEW_PACKAGE}.Main"' in body
    assert OLD_PACKAGE not in body

    library = (root / "lib" / "arm64-v8a" / "libgrowtopia.so").read_bytes()
    assert OLD_PACKAGE.encode() not in library
    assert b"com.rtsoft." not in library
    assert b"com/rtsoft/growtopia" not in library
    assert NEW_PACKAGE.encode() in library
    assert b"com.dev_rt." in library
    assert b"com/dev_rt/growtopia/Main" in library
    assert b"Java_com_rtsoft_growtopia_Main" in library

    yml = (root / "apktool.yml").read_text(encoding="utf-8")
    assert "- AndroidManifest.xml" in yml
    assert f"renameManifestPackage: {NEW_PACKAGE}" in yml
    assert report.total > 0
    assert any("Full rename" in warning for warning in report.warnings)
    assert any("not migrated" in warning for warning in report.warnings)


def test_apply_rename_replaces_server_hosts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "cloneclient.infrastructure.rename_engine.rename_jni_symbols",
        lambda *args: 0,
    )
    root = make_tree(tmp_path)
    plan = build_rename_plan(NEW_PACKAGE)
    first = "www.example001.com"
    second = "www.example002.com"

    report = apply_rename(
        root,
        plan,
        server_replacements=((SERVER_1, first), (SERVER_2, second)),
    )

    library_path = root / "lib" / "arm64-v8a" / "libgrowtopia.so"
    library = library_path.read_bytes()
    assert SERVER_1.encode() not in library
    assert SERVER_2.encode() not in library
    assert first.encode() in library
    assert second.encode() in library
    assert any("server1" in line for line in report.to_lines())
    assert any("server2" in line for line in report.to_lines())
