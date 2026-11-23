# Implementation Plan

Source: `SPEC.md`

Catatan: Plan di file ini adalah plan fondasi. Fitur utama XAPK Repackager sudah diimplementasikan: full rename, LIEF JNI symbol rewrite, patch partial `com.rtsoft.`, verifikasi manifest/dex/native/layout/signature, dan device run. Detail di `.mandor/agents/memory/main.md`.
Status: implemented (fondasi, slice Diagnostics, slice Settings/Theme, crash handler, fitur utama XAPK Repackager)
Tanggal: 2026-11-22

## Hasil implementasi

Keputusan yang dipakai saat implementasi:
- D1: dikonfirmasi user. Package `cloneclient`, app dan exe `CloneClient`, versi `0.1.0`.
- D2: dikonfirmasi user, fitur pertama adalah layar Diagnostics dengan aksi copy ke clipboard.
- D4: persistence diimplementasikan untuk window geometry dan theme di `%LOCALAPPDATA%\cloneclient\settings.json`.

Status task:
- T1 sampai T11: selesai.
- T12: slice Settings/Theme selesai: pilihan Light/Dark, persistence theme dan geometry, test UI dan service.
- T13: verifikasi crash handler selesai: unit test dan flag `--crash-test`.
- Code signing diputuskan ditunda sampai setelah 1.0 dan dicatat di `SPEC.md`.

Bukti verifikasi:
- `uv run ruff check src tests scripts build.py` lulus.
- `uv run ruff format --check src tests scripts build.py` lulus.
- `uv run pytest` lulus 18 test.
- `uv run python scripts/check_style.py` lulus.
- `uv run python build.py` menghasilkan `dist/CloneClient.exe` 45.2 MB.
- `dist/CloneClient.exe --smoke` exit 0 dengan PATH tanpa Python.
- `dist/CloneClient.exe --crash-test` exit 1, traceback tercatat di `cloneclient.log`.
- Smoke menulis `%LOCALAPPDATA%\cloneclient\settings.json` berisi theme dan window geometry.

## Slice tambahan

- T12 Settings/Theme: `QComboBox` Light/Dark, `ui/theme.py`, merge persistence di `SettingsService`, test domain, service, dan UI.
- T13 Crash handler: `tests/unit/test_logging_setup.py` dan `--crash-test` yang memanggil `sys.excepthook`.

## Ringkasan requirement

Fondasi aplikasi desktop GUI Python (PySide6) yang berlayer, reproducible dengan uv, dan bisa dibuild menjadi satu `.exe` Windows x64 yang jalan tanpa Python. Gaya kode: English, tanpa emoji, tanpa U+2014, komentar menjelaskan alasan.

## Boundary dan kondisi saat ini

- Greenfield: belum ada kode aplikasi, hanya `SPEC.md`, `.commandcode/`, `.opencode/`, `.mandor/`.
- Kode aplikasi tidak boleh dicampur ke `.commandcode/` atau `.opencode/`.
- `domain` tidak boleh import `ui`, `services`, atau `infrastructure`.
- Build hanya di Windows x64.

## Decision gate

- **D1. Identitas app**: nama package, nama exe, icon, versi. Memblokir T1 dan T6.
- **D2. Fitur pertama**: satu alur nyata untuk slice vertikal. Memblokir T9 dan T10.
- **D3. Versi Python**: rekomendasi 3.12.x. Memblokir T1.
- **D4. Storage**: perlu persistence di fitur pertama atau belum. Menentukan T10.
- **D5. Type checker**: mypy, pyright, atau belum. Tidak memblokir, hanya melengkapi T2.
- **D6. Code signing**: sekarang atau nanti. Tidak memblokir fondasi, relevan di T11.

## Dependency graph

```
D1, D3 -> T1 -> T2, T3, T4
T3 -> T5 -> T6 -> T7
T2, T6 -> T8 (opsional)
T3, T4, D2 -> T9 -> T10 (jika D4 butuh storage)
T6, D6 -> T11 (nanti)
```

## Phase 1: Fondasi

### T1. Scaffold proyek

- **Description**: Inisialisasi `pyproject.toml` untuk uv, package `src/<app>/`, `__main__.py`, `.gitignore`, `README.md`.
- **Acceptance**: `uv sync` sukses; `python -m <app>` menjalankan stub tanpa error.
- **Verify**: `uv sync`, `python -m <app>`.
- **Files**: `pyproject.toml`, `src/<app>/__init__.py`, `src/<app>/__main__.py`, `.gitignore`, `README.md`.
- **Depends**: D1, D3.
- **Scope**: S.

### T2. Tooling kualitas

- **Description**: Konfigurasi `ruff` dan `pytest`, plus `scripts/check_style.py` yang memindai source dan docs untuk emoji dan U+2014.
- **Acceptance**: `ruff check`, `ruff format --check`, `pytest`, dan `python scripts/check_style.py` lulus pada stub.
- **Verify**: jalankan keempat perintah.
- **Files**: `pyproject.toml`, `scripts/check_style.py`, `tests/unit/`.
- **Depends**: T1.
- **Scope**: S.

### T3. Skeleton PySide6

- **Description**: Entry point membuat `QApplication` dan `MainWindow` minimal; logika wiring ada di `bootstrap.py`, bukan di `__main__.py`.
- **Acceptance**: GUI terbuka dan tertutup bersih dengan exit code 0.
- **Verify**: `python -m <app>`, tutup jendela, cek exit code.
- **Files**: `src/<app>/__main__.py`, `src/<app>/bootstrap.py`, `src/<app>/ui/main_window.py`.
- **Depends**: T1.
- **Scope**: S.

### T4. Batas layer dan import test

- **Description**: Buat package `domain/`, `services/`, `infrastructure/`, `shared/` dengan isi minimal, lalu tes yang memastikan `domain` tidak import layer lain.
- **Acceptance**: import test lulus; struktur mengikuti dependency `ui -> services -> domain` dan `infrastructure -> domain`.
- **Verify**: `pytest tests/unit/test_import_rules.py`.
- **Files**: `src/<app>/domain/__init__.py`, `src/<app>/services/__init__.py`, `src/<app>/infrastructure/__init__.py`, `src/<app>/shared/__init__.py`, `tests/unit/test_import_rules.py`.
- **Depends**: T1.
- **Scope**: S.

### T5. Paths, logging, crash handler

- **Description**: Modul `infrastructure/paths.py` untuk `%LOCALAPPDATA%` atau `%APPDATA%` (tanpa dependency baru), logging ke file, dan global exception hook yang menulis traceback lalu menampilkan pesan ke user.
- **Acceptance**: log file dibuat di user data dir; exception tak tertangani tercatat dan aplikasi tidak crash diam-diam.
- **Verify**: jalankan skenario exception yang disengaja, cek file log.
- **Files**: `src/<app>/infrastructure/paths.py`, `src/<app>/infrastructure/logging_setup.py`, `src/<app>/bootstrap.py`.
- **Depends**: T3.
- **Scope**: S.

### T6. Build pipeline single-file exe

- **Description**: `build/app.spec` dan `build.py` untuk PyInstaller onefile `--windowed`, icon dan version info.
- **Acceptance**: `python build.py` menghasilkan `dist/<App>.exe` satu file; exe terbuka di mesin build.
- **Verify**: `python build.py`, jalankan `dist/<App>.exe`.
- **Files**: `build/app.spec`, `build.py`, `assets/app.ico`, `build/version_info.txt`.
- **Depends**: T3, T5.
- **Scope**: M.

### T7. Verifikasi mesin bersih

- **Description**: Checklist dan skrip bantu untuk menjalankan exe di Windows x64 tanpa Python, termasuk path berspasi dan non-ASCII.
- **Acceptance**: exe jalan di VM/container tanpa `python.exe`; tidak ada error DLL atau asset hilang.
- **Verify**: jalankan checklist di clean Windows.
- **Files**: `docs/verification.md`, opsional `scripts/verify_build.py`.
- **Depends**: T6.
- **Scope**: S.

### T8. CI Windows (opsional)

- **Description**: Workflow GitHub Actions di Windows untuk `ruff`, `pytest`, `check_style.py`, dan build.
- **Acceptance**: workflow hijau dan menghasilkan artefak `dist/<App>.exe`.
- **Verify**: jalankan workflow.
- **Files**: `.github/workflows/ci.yml`.
- **Depends**: T2, T6.
- **Scope**: S.
- **Catatan**: hanya jika repo akan dipakai dengan GitHub Actions.

## Phase 2: Slice fitur pertama

### T9. Fitur pertama end-to-end

- **Description**: Implementasi satu alur nyata: aturan di `domain`, orchestration di `services`, UI dan viewmodel di `ui`, wiring di `bootstrap.py`.
- **Acceptance**: unit test domain lulus, smoke test UI dengan `pytest-qt` lulus, dan alur jalan di exe.
- **Verify**: `pytest tests/unit tests/ui`, `python build.py`, uji manual.
- **Files**: `src/<app>/domain/*.py`, `src/<app>/services/*.py`, `src/<app>/ui/*.py`, `tests/unit/`, `tests/ui/`.
- **Depends**: T3, T4, D2.
- **Scope**: M atau L, pecah bila lebih dari 5 file.

### T10. Persistence fitur pertama (jika D4 perlu)

- **Description**: Definisikan port di layer yang butuh (domain atau services), implementasi adapter di `infrastructure`, dan test adapter.
- **Acceptance**: port dan adapter terpisah; test adapter lulus; domain tetap tanpa import infrastructure.
- **Verify**: `pytest tests/unit tests/integration`.
- **Files**: `src/<app>/domain/ports.py` atau `services/ports.py`, `src/<app>/infrastructure/*.py`, `tests/integration/`.
- **Depends**: T9, D4.
- **Scope**: M.

## Phase 3: Rilis (nanti)

### T11. Hardening rilis

- **Description**: Versioning, changelog, keputusan code signing, catatan SmartScreen, dan pengecekan ukuran serta waktu start.
- **Acceptance**: versi exe terbaca, changelog ada, keputusan signing terdokumentasi.
- **Verify**: cek properties exe, ukuran, waktu start.
- **Files**: `build/version_info.txt`, `CHANGELOG.md`, `docs/release.md`.
- **Depends**: T6, D6.
- **Scope**: S.

## Verifikasi global

- `uv sync`
- `ruff check` dan `ruff format --check`
- `pytest`
- `python scripts/check_style.py`
- `python build.py`
- Jalankan exe di clean Windows x64 tanpa Python

## Memory gaps

- Nama app dan package belum ada.
- Fitur pertama belum didefinisikan, sehingga T9 dan T10 belum bisa dimulai.
- Kebutuhan storage belum jelas.
