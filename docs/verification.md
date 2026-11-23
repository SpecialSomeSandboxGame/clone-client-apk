# Verification

Run these checks on Windows x64.

## Local checks

1. `uv sync`
2. `uv run python scripts/fetch_tools.py`
3. `uv run python scripts/fetch_jdk.py`
4. `uv run python -m cloneclient --tool-check`
5. `uv run python -m cloneclient --inspect ".cache/Growtopia_5.62_dev (3).xapk"`
6. `uv run pytest`
7. `uv run ruff check src tests scripts build.py`
8. `uv run ruff format --check src tests scripts build.py`
9. `uv run python scripts/check_style.py`
10. `uv run python build.py`

`--tool-check` also imports LIEF and Pillow and reports their versions, so a broken image or ELF extension is caught before a repack.

## Repack end-to-end

1. `CLONECLIENT_RUN_SLOW=1 uv run pytest tests/integration/test_repack_pipeline.py -q`
2. The test fails if the manifest, dex, native dynamic symbols, layout, or signature checks fail.
3. Produce an APK with the GUI, or use the verified artifact from a manual run.
4. Install it with `adb install -r --no-streaming <output.apk>`.
5. Start it with `adb shell am start -W -n com.dev_rt.growtopia/com.dev_rt.growtopia.Main`.
6. Confirm the process exists with `adb shell pidof com.dev_rt.growtopia`.
7. Confirm `Main` is resumed with `adb shell dumpsys activity activities | findstr com.dev_rt`.
8. Confirm SurfaceView frames with `adb logcat -d | findstr "SurfaceView[com.dev_rt"`.
9. Inspect `adb logcat -d -b crash -t 100` for `FATAL EXCEPTION`, `UnsatisfiedLinkError`, `SIGSEGV`, or `SIGABRT`.

On some Xiaomi or HyperOS devices, ADB install is blocked until the shell installer is allowed:

```bash
adb shell appops set com.android.shell REQUEST_INSTALL_PACKAGES allow
```

## Expected findings

- The manifest package, component names, authorities, and permissions use `com.dev_rt.growtopia`.
- Java classes and smali directories use `com.dev_rt.growtopia`; `classes*.dex` has no old package references.
- `libgrowtopia.so` has no old full package, path, or `com.rtsoft.` prefix strings.
- `libgrowtopia.so` has 0 old dynamic JNI symbols and 32 new `Java_com_dev_1rt_growtopia_*` dynamic symbols.
- Old `Java_com_rtsoft_growtopia_*` text may remain in `.rodata` as string literals. The verifier allows them because they are not dynamic symbols and are not used for lookup.
- When an app name was requested, the application and launcher labels match it. When an icon was requested, `android:icon` and `android:roundIcon` use `@mipmap/cloneclient_icon` and the APK contains five mipmap PNGs.
- The new data path is `Android/data/com.dev_rt.growtopia`. Old data under `Android/data/com.rtsoft.growtopia` is not migrated.
- The APK is signed with the generated release keystore and passes zipalign and signature verification.

## Same-package control

To separate a package rename failure from a signature or rebuild failure:

1. Build an APK with the original package name and no rename.
2. Sign it with the same test keystore.
3. Install it after uninstalling the original app.
4. Launch it and confirm GameThread and SurfaceView run.

This control was executed on the test device. It ran normally, which proved the signature and apktool rebuild were not the cause of the earlier GameThread crash. The crash came from the package name, not the signing key.

## Original app backup and restore

Before the same-package control, the original split APKs and external data were backed up:

- `.cache/original-app/` contains `base.apk` and the split APKs.
- `.cache/original-data/` contains the external `cache` and `files` directories.

Restore with:

```bash
adb uninstall com.rtsoft.growtopia
adb install-multiple --no-streaming .cache/original-app/base.apk .cache/original-app/split_config.arm64_v8a.apk .cache/original-app/split_config.en.apk .cache/original-app/split_config.xxhdpi.apk
adb push .cache/original-data/ /sdcard/original-data-restore/
adb shell mkdir -p /sdcard/Android/data/com.rtsoft.growtopia
adb shell cp -r /sdcard/original-data-restore/. /sdcard/Android/data/com.rtsoft.growtopia/
adb shell rm -rf /sdcard/original-data-restore
```

Internal app data is removed by uninstall and is not part of the backup.

## Recorded evidence

- Fast checks: 76 tests passed, 1 slow test skipped.
- Bundled runtime: Temurin 21 minimal, 46.5 MB, contains `java` and `keytool`; the slow repack passed using it.
- Slow end-to-end test: exit code 0 with full rename, app name/icon, native server endpoints, and verification.
- Server endpoint test data used `www.example001.com` and `www.example002.com`; the old hosts were absent from `libgrowtopia.so` and the new hosts were present after the repack.
- Device run of the full rename build:
  - `pidof com.dev_rt.growtopia` returned a live PID.
  - `topResumedActivity` was `com.dev_rt.growtopia/.Main`.
  - SurfaceView frames were produced at about 59 fps.
  - Crash buffer was empty.
- The working artifact used for that device run was `.cache/full-rename/full-rename-fix.apk`.

## Clean machine

1. Copy `dist/CloneClient.exe` to a Windows x64 machine without Python or Java.
2. Run the executable from a path that contains spaces.
3. Confirm the window opens and the Diagnostics tab renders.
4. Confirm the log file appears under `%LOCALAPPDATA%\cloneclient\logs`.
5. Confirm `%LOCALAPPDATA%\cloneclient\settings.json` is written after the window closes.
6. Run `dist\CloneClient.exe --smoke` and confirm the process exits with code 0.
7. Run `dist\CloneClient.exe --crash-test` and confirm exit code 1 plus a logged traceback.
8. Run `dist\CloneClient.exe --tool-check` and confirm the report points `java` and `keytool` at the extracted `runtime\bin` directory, not a host JDK.
9. Run one repack on the clean machine and confirm it completes with the bundled runtime.

## Release checks

- The one-file executable is around 122 MB and includes the 46.5 MB Temurin runtime.
- Version metadata in the executable matches the release version.
- Ship `THIRD_PARTY_NOTICES.md`; the runtime license files are under `runtime/legal` inside the executable.
- SmartScreen may warn because the executable is unsigned. Record this as an expected warning, not a defect.
