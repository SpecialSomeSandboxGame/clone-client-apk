# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
RUNTIME = ROOT / "runtime"
datas = [(str(TOOLS), "tools")] if TOOLS.exists() else []
datas += [(str(RUNTIME), "runtime")] if RUNTIME.exists() else []
datas += collect_data_files("pyaxmlparser")

a = Analysis(
    [str(SRC / "cloneclient" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "lief",
        "lief._lief",
        "PIL._webp",
        "pyaxmlparser",
        "pyaxmlparser.axmlprinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CloneClient",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(ROOT / "build" / "version_info.txt"),
    icon=None,
)
