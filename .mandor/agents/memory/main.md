# Project Memory

## Overview

Repository ini adalah proyek aplikasi desktop GUI Python (CloneClient) yang dibundel menjadi `.exe` Windows x64. Fitur utama XAPK/APK repackager sudah diimplementasikan dan diverifikasi di device. Tool menerima satu XAPK/APK, merge split dengan APKEditor, full rename package Java, manifest, resource, string native, dan JNI symbols ke `com.dev_rt.growtopia`, lalu sign dan verify. Output final ada di `output/Growtopia_5.62_dev_3_-5.62-dev.apk`.

UX Repack tab sudah di-redesign berdasarkan riset Exa: satu page scroll, satu primary action per state, progress yang baru muncul saat run, checklist yang hanya menampilkan blocker, details on demand, inline validation, cancel, dan keyboard shortcuts. Screenshot state ada di `docs/ux-*.png`; rationale dan state model di `docs/ux.md`.

`dist/CloneClient.exe` 0.5.0 berukuran 122.7 MB (122.660.832 byte) dan sudah self-contained: runtime Temurin 21 minimal 46.5 MB, JAR, LIEF, dan Pillow dibundel. `--tool-check` melaporkan `java` dan `keytool` dari `_MEI...\runtime\bin`, `pillow: 13.0.0`, `--smoke` dan `--inspect` exit 0, `--crash-test` exit 1 dengan traceback. Tidak perlu JDK host dan tidak perlu network saat runtime.

## Layout

- `.commandcode/AGENTS.md` - aturan primary agent Mandor; dimuat Command Code sebagai project memory.
- `.commandcode/agents/mandor.md` - subagent `mandor` untuk delegasi; menginstruksikan pembacaan `AGENTS.md`.
- `.commandcode/commands/` - slash command: build, code-simplify, planning, review, ship, spec, test.
- `.commandcode/skills/` - 25 Agent Skills (salinan `.opencode/skills/`, path internal sudah diarahkan ke `.commandcode/`).
- `.commandcode/references/definition-of-done.md` - gate penyelesaian proyek.
- `.commandcode/settings.json` - permission project.
- `.mcp.json` - MCP server `agent-toolkit` (stdio) dan `exa` (http, header `x-api-key: ${EXA_API_KEY}`).
- `.opencode/` - konfigurasi OpenCode asal; dipertahankan sebagai sumber, tidak dibaca Command Code.
- `SPEC.md` - spec fitur utama: full rename, LIEF JNI, patch partial `com.rtsoft.`, signing, verifikasi.
- `docs/specs/foundation.md` - arsip spec fondasi Python GUI dan packaging exe.
- `docs/ux.md` - riset UX, audit UI lama, state model, keputusan desain, dan bukti screenshot.
- `docs/ux-idle.png`, `ux-ready.png`, `ux-busy.png`, `ux-failed.png`, `ux-success.png` - screenshot state Repack tab.
- `docs/verification.md` - langkah verifikasi, termasuk device run dan backup restore.
- `.cache/` - tiga XAPK contoh Growtopia 5.62, backup app original, backup data eksternal, dan APK same-package; tidak untuk di-commit.
- `.mandor/agents/rules.md` - aturan gaya proyek: kode English, tanpa emoji, tanpa em dash U+2014, komentar menjelaskan alasan.
- `.mandor/agents/tasks/plan.md` - plan fondasi; fitur utama sudah diimplementasikan.
- `src/cloneclient/` - package berlayer: `ui`, `services`, `domain`, `infrastructure`, `shared`.
- `src/cloneclient/ui/repackager_view.py` - workflow Repack dengan state, validasi, cancel, shortcuts, dan details panel.
- `src/cloneclient/infrastructure/jni_rename.py` - LIEF dynamic symbol renamer.
- `src/cloneclient/infrastructure/native_patch.py` - in-place package/prefix patcher.
- `src/cloneclient/infrastructure/toolchain.py` - discovery Java/keytool tanpa `shutil.which` (PATH bisa hang) dan cache versi Java.
- `tests/` - unit, integration, dan slow end-to-end test.
- `tools/` - JAR pinned: APKEditor 1.4.9, apktool 3.0.3, uber-apk-signer 1.3.0.
- `build/` - spec PyInstaller dan version info.
- `output/` - APK hasil pipeline final.

## Commands

- `uv sync`
- `uv run python scripts/fetch_tools.py` - download atau verifikasi JAR.
- `uv run python -m cloneclient --tool-check`
- `uv run python -m cloneclient --inspect "<xapk>"`
- `uv run pytest`
- `CLONECLIENT_RUN_SLOW=1 uv run pytest tests/integration/test_repack_pipeline.py -q`
- `uv run python build.py`
- `cmdc skills list`, `cmdc mcp list`

## Decisions

- Primary agent OpenCode (`mode: primary`) dipetakan ke `.commandcode/AGENTS.md` karena Command Code tidak punya setting default primary agent.
- Permission OpenCode dipetakan ke `defaultMode: accept-edits` + allow perintah git read, `mcp__agent-toolkit__*`, dan `mcp__exa__*`.
- Exa remote MCP `https://mcp.exa.ai/mcp` dengan API key dari environment `EXA_API_KEY`.
- `subagent_depth`, `agent.plan/build disable`, dan plugin OpenCode tidak punya padanan langsung.
- Skill `browser-testing-with-devtools` masih butuh MCP `chrome-devtools`; belum ditambahkan.
- Stack: Python 3.12, PySide6, PyInstaller onefile Windows x64, uv, layer `ui -> services -> domain`, `infrastructure -> domain`.
- Full rename package dipilih setelah device test:
  - Same-package APK dengan signature test key berjalan, jadi signature bukan penyebab crash.
  - Rename applicationId tanpa rename class crash `SIGSEGV` di GameThread.
  - Full rename tanpa rename JNI abort `ClassNotFoundException: com.rtsoft.growtopia.Main`.
  - LIEF rename 32 simbol JNI plus patch potongan `com.rtsoft.` membuat app berjalan.
- `libgrowtopia.so` masih menyimpan 28 string literal JNI lama di `.rodata`; verifier hanya mewajibkan 0 old **dynamic symbols** dan 32 new dynamic symbols.
- Package baru `com.dev_rt.growtopia` (20 karakter) dan potongan `com.dev_rt.` (11 karakter) dipilih agar patch native in-place aman. Validasi sekarang mewajibkan panjang penuh dan potongan sama persis dengan package lama; selisih ditolak sebelum pipeline.
- Keystore password minimal 6 karakter, mengikuti batas `keytool`; input UI dan service menolak password lebih pendek sebelum proses.
- Data pengguna lama tidak dimigrasikan. App baru memakai `Android/data/com.dev_rt.growtopia` dan dimulai dengan data fresh.
- Keystore release digenerate dengan `keytool`; password diminta saat proses dan tidak disimpan.
- JAR dibundel dan diverifikasi SHA-256. LIEF dan `pyaxmlparser` masuk dependency Python; `public.xml` harus dikumpulkan dengan `collect_data_files("pyaxmlparser")` di PyInstaller.
- Exe self-contained memakai runtime Temurin 21.0.13.1+2 hasil `jlink` (`java.base,java.desktop,java.logging`, 46.5 MB, berisi `java` dan `keytool`). `scripts/fetch_jdk.py` mengunduh JDK pinned dengan SHA-256, `build.py` membangun/membundel `runtime/`, dan `toolchain._bundled_java` memilih runtime itu sebelum JDK host. `runtime/` masuk `.gitignore`; lisensi runtime dicatat di `THIRD_PARTY_NOTICES.md`.
- UX redesign: satu page scroll (bukan dua scrollbar), footer aksi tetap, progress card hanya tampil saat run, checklist blocker-only, details on demand, primary action per state (`Repack APK`, `Repacking...`, `Try again`, `Repack another`), inline validation, cancel, `Ctrl+O`/`Ctrl+R`/`Esc`, dan fokus awal di field source. Inline validation mencakup panjang application id dan minimum 6 karakter keystore password.
- Appearance opsional: app name literal ke `android:label` application dan launcher; icon PNG/JPG/WebP minimal 48x48 di-center-crop ke lima `mipmap-*` sebagai `cloneclient_icon`, lalu `android:icon`/`android:roundIcon` diarahkan ke resource itu. UI punya Appearance card, preview 64 px, Clear, dan blocker inline. Verifier meresolve resource ID icon yang sudah dikompilasi lewat `pyaxmlparser.APK.get_app_icon()` karena manifest AXML tidak menyimpan nama `@mipmap/...`.
- Server endpoint opsional: Server 1 dan Server 2 mengganti `www.growtopia1.com` dan `www.growtopia2.com` di native library. Nilai harus tepat 18 karakter, ASCII, tanpa spasi; kosong berarti tetap. UI punya Server endpoints card; `rename_engine` menerima `server_replacements`; verifier punya `check_server_strings`.
- Toolchain discovery memilih runtime bundel lebih dulu, lalu JAVA_HOME, javapath, dan scan direktori JDK lokal. `shutil.which` tidak dipakai karena PATH di mesin ini bisa menggantung lama. Versi Java di-cache agar cek tool tidak menjalankan `java -version` dua kali.
- Verifikasi UX, validasi, appearance, server endpoint, dan runtime terakhir: 76 test cepat lulus, 1 slow opt-in skip; slow end-to-end dengan app name/icon, Server 1/2, dan runtime bundel lulus; ruff/format/style lulus; exe 0.5.0 122.7 MB; `--tool-check` melaporkan runtime, Pillow 13.0.0, dan keytool; screenshot `docs/ux-appearance.png` menunjukkan validasi nama/icon.
- Device: APK output tool terpasang dan berjalan (PID hidup, `Main` resumed, SurfaceView sekitar 57-59 fps, crash buffer kosong).
- Device cleanup: app original `com.rtsoft.growtopia` di-uninstall untuk same-package test. Reinstall via ADB diblokir MIUI `INSTALL_FAILED_USER_RESTRICTED`. Backup ada di `.cache/original-app/` (split APK), `.cache/original-data/` (data eksternal), dan `.cache/same-package-test/same-package-test.apk`. User perlu mengaktifkan Install via USB atau install ulang dari Play Store. Data internal original hilang saat uninstall.
