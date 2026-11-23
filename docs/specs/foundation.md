# Spec: Python Desktop GUI menuju Standalone Windows `.exe`

Status: approved
Tanggal: 2026-11-22

## 1. Objective

Seluruh proyek ditulis dengan Python sebagai aplikasi desktop GUI, lalu didistribusikan sebagai satu file `.exe` Windows x64 yang berjalan tanpa Python terpasang. Fondasi harus fleksibel untuk pertumbuhan fitur, tetapi tidak membangun abstraksi untuk kebutuhan yang belum terbukti.

## 2. Users

- End user Windows 10/11 x64 tanpa Python.
- Developer yang menulis kode dan menjalankan build.
- CI Windows x64 (opsional).

## 3. Prinsip desain

1. `src/` layout, package per domain, `tests/` di luar `src/`.
2. Layer terpisah: `ui`, `services`, `domain`, `infrastructure`. Dependency hanya ke bawah.
3. `domain` murni: tanpa import UI, filesystem, atau network. Bisa diuji tanpa GUI.
4. Abstraksi hanya di titik yang benar-benar berubah (storage, external API, config), bukan di semua tempat.
5. Rule of Three sebelum generalisasi; YAGNI untuk fitur hipotetis.
6. Verifikasi cepat: slice vertikal kecil, jalankan test, baru lanjut.

## 4. Tech stack

- **Python:** 3.12.x, pinned.
- **GUI:** PySide6 (Qt) untuk signal/slot, struktur MVVM, dan `pytest-qt`.
- **Packaging:** PyInstaller mode onefile, `--windowed`, Windows x64, `.spec` di-commit.
- **Dependency manager:** `uv` + `pyproject.toml`/`uv.lock`.
- **Quality:** `ruff` untuk format dan lint, plus script gaya proyek. Type checker `mypy`/`pyright` opsional (`open decision`).

## 5. Struktur proyek usulan

```
pyproject.toml
uv.lock
README.md
src/<app>/
  __main__.py
  bootstrap.py          # composition root, wiring dependency
  ui/                   # views, viewmodels, widgets
  services/             # use case / orchestration
  domain/               # model dan aturan murni
  infrastructure/       # storage, config, external API
  shared/               # tipe, error, konstanta kecil
build/
  app.spec
build.py                # helper build, Python
assets/
tests/
  unit/
  integration/
  ui/
scripts/
  check_style.py
SPEC.md
```

Aturan dependency:

- `ui` -> `services` -> `domain`
- `infrastructure` -> `domain` (implementasi port bila ada)
- `domain` tidak import `ui`, `services`, atau `infrastructure`
- `bootstrap.py` merangkai semuanya

## 6. Berpikir tiga langkah ke depan

Sumbu perubahan yang realistis: toolkit GUI, format storage, layanan eksternal, format distribusi, dan fitur produk.

- Taruh seam hanya di sumbu yang benar-benar berisiko berubah (storage, external API, config). Gunakan `Protocol`/ABC di sana, bukan di seluruh aplikasi.
- `domain` tetap UI-agnostic, sehingga view bisa diganti dan diuji terpisah.
- Build diisolasi di `build/app.spec`, supaya ganti packaging tidak menyentuh kode aplikasi.
- Jangan tambah event bus, plugin system, atau layer generik sebelum ada use case kedua yang nyata.
- Kembangkan lewat slice vertikal kecil dan feedback loop pendek.

## 7. Gaya kode dan komentar

- Semua kode dan komentar dalam bahasa Inggris.
- Tanpa emoji di mana pun.
- Tanpa karakter em dash (U+2014) di mana pun.
- Komentar menjelaskan alasan, constraint, atau trade-off; tidak mengulang kode dan tidak bercerita tutorial.
- TODO harus menyebut apa yang tertunda dan mengapa.
- `scripts/check_style.py` memindai source dan docs untuk emoji dan U+2014, lalu gagal di CI bila ditemukan.

## 8. Acceptance criteria

- [ ] `python -m <app>` menjalankan GUI dari source.
- [ ] `python build.py` menghasilkan `dist/<App>.exe` satu file.
- [ ] Di Windows x64 tanpa Python, `.exe` membuka GUI dan alur inti berjalan.
- [ ] Tidak ada dependensi ke `python3xx.dll` eksternal dan tidak ada asset yang hilang.
- [ ] `scripts/check_style.py` lulus: tanpa emoji, tanpa U+2014.
- [ ] Semua identifier, komentar, docstring, dan log dalam bahasa Inggris.
- [ ] Logika `domain` punya unit test tanpa GUI; ada smoke test UI.
- [ ] Arah dependency terjaga (bisa dicek dengan import test).
- [ ] `dist/`, `build/`, dan cache masuk `.gitignore`.

## 9. Verification

- Build di Windows x64, cek ukuran dan waktu start `dist/<App>.exe`.
- Jalankan di clean Windows VM/container tanpa `python.exe`.
- `pytest`, `ruff check`, `ruff format --check`, `python scripts/check_style.py`.
- Uji dari path berspasi dan non-ASCII, serta mode offline.
- Catat bahwa `.exe` unsigned memicu peringatan SmartScreen, bukan bug.

## 10. Constraints

- Build harus di Windows x64; PyInstaller tidak cross-compile.
- Onefile mengekstrak ke temp, jadi aplikasi hanya menulis ke `%LOCALAPPDATA%` atau `%APPDATA%`.
- Tanpa admin, tanpa requirement Python di mesin target.
- Budget ukuran: PySide6 di bawah 150 MB. Build saat ini 45.2 MB.
- Logging dan crash handler wajib, menulis ke user data dir.

## 11. Decisions

Sudah diputuskan:
- GUI: PySide6 (Qt).
- Dependency manager: uv.
- Python: 3.12.
- App: nama tampilan dan exe `CloneClient`, package `cloneclient`, versi `0.1.0` (D1 dikonfirmasi user).
- Storage: JSON `settings.json` di `%LOCALAPPDATA%\cloneclient` untuk window geometry dan theme.
- Fitur pertama: layar Diagnostics (info runtime plus copy) sebagai slice fondasi.
- Slice kedua: Settings/Theme dengan pilihan Light dan Dark.
- Crash handler: dipasang di event loop dan diverifikasi lewat unit test serta flag `--crash-test` (exit 1, traceback tercatat di log).
- Code signing: ditunda sampai setelah 1.0. Build unsigned dan peringatan SmartScreen diterima.
- Budget ukuran: 45.2 MB, di bawah 150 MB.

Masih terbuka dan butuh keputusan user:
- Icon final app.
- Type checker.

## 12. Boundaries

- **Always:** build dari `.spec`, uji di mesin bersih, jaga dependency mengalir ke bawah, gitignore artefak.
- **Ask first:** tambah dependency berat, ganti toolkit atau packaging, aktifkan code signing.
- **Never:** commit `.exe` atau secret, butuh admin, tulis ke Program Files atau cwd saat runtime.

## Referensi riset

- Python project layout: https://realpython.com/ref/best-practices/project-layout/
- src vs flat layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- Python package structure: https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html
- Layered architecture contoh: https://www.cosmicpython.com/book/appendix_project_structure
- Future-proofing dan YAGNI: https://peterdahlgren.com/itdepends/future-proofing/
- Rule of Three: https://matthewboston.com/blog/over-engineering-is-just-future-proofing-gone-too-far.html
- Komentar kode: https://geodemcp.com/blog/comments-in-code
- Komentar dan AI: https://webdelo.com/blog/code-comments-ai-coding-agents
- Arsitektur GUI Python: https://physicslabs.colorado.edu/courses/python/lab-software/lab-app-architecture
- Testing PySide6: https://schoolofweb.net/en/posts/pyside6-practice-7/
- Tanda tulisan AI: https://www.pangram.com/signs-of-ai-writing
