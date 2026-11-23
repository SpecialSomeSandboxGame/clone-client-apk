# Spec: CloneClient XAPK Repackager

Status: approved
Tanggal: 2026-11-22

## 1. Objective

Membangun fitur utama CloneClient: aplikasi desktop GUI Python dan PySide6 yang menerima satu file XAPK atau APK, menampilkan diagnostik aplikasi, menggabungkan split APK di dalam XAPK menjadi satu APK biasa, memindahkan applicationId, package Java, manifest, resource, string native, dan simbol JNI dari `com.rtsoft.growtopia` ke `com.dev_rt.growtopia`, lalu menghasilkan APK bertanda tangan yang berjalan di device.

## 2. Users

- Developer atau operator yang menjalankan tool.
- End user yang menerima APK hasil, tanpa menjalankan tool.

## 3. Input contoh

Tiga XAPK contoh ada di `.cache`:

- `Growtopia_5.62_dev (1).xapk`: 20 APK, ABI `armeabi_v7a`, density `hdpi`, banyak bahasa, minSdk 29.
- `Growtopia_5.62_dev (2).xapk`: 20 APK, ABI `arm64_v8a`, density `xxxhdpi`, banyak bahasa, minSdk 29.
- `Growtopia_5.62_dev (3).xapk`: 4 APK, ABI `arm64_v8a`, density `mdpi`, bahasa `en`, minSdk 32.

Semua memakai package `com.rtsoft.growtopia`, version 5.62 (428), dan tidak memiliki OBB.

Temuan string package lama:

- `classes2.dex`: 112 kemunculan `com/rtsoft/growtopia` dan 2 kemunculan `com.rtsoft.growtopia`.
- `classes.dex`: 15 kemunculan `com/rtsoft/growtopia`.
- `classes3.dex`: 1 kemunculan `com.rtsoft.growtopia`.
- `classes4.dex`: 2 kemunculan `com.rtsoft.growtopia`.
- `lib/arm64-v8a/libgrowtopia.so`: 15 kemunculan `com.rtsoft.growtopia`, 11 kemunculan `com/rtsoft/growtopia`, dan 1 potongan `com.rtsoft.` yang dipakai untuk menyusun nama class.
- `AndroidManifest.xml` dan `resources.arsc` memakai UTF-16, jadi harus diproses lewat apktool atau aapt, bukan replace teks ASCII.

Temuan JNI dari pengujian di device:

- `libgrowtopia.so` mengekspor 32 simbol dinamis `Java_com_rtsoft_growtopia_*` dan string class `com/rtsoft/growtopia/...`.
- Rename package Java tanpa rename simbol JNI menghasilkan `UnsatisfiedLinkError` atau abort `ClassNotFoundException`.
- Rename JNI dengan replace byte tidak cukup karena hash ELF masih memakai nama lama. LIEF dipakai untuk menulis ulang dynamic symbol table dan hash.
- Setelah LIEF rename, `.so` masih memuat potongan `com.rtsoft.` yang dipakai native code untuk membentuk nama class. Potongan itu juga harus diganti.
- Setelah full rename plus patch `com.rtsoft.`, app berjalan: PID hidup, `Main` resumed, SurfaceView render sekitar 59 fps, dan crash buffer kosong.

Temuan isolasi:

- APK same-package dengan signature test key berjalan normal. Signature bukan penyebab crash.
- Rename applicationId saja, tanpa rename class, crash `SIGSEGV` di GameThread.
- Full rename tanpa rename JNI abort `ClassNotFoundException: com.rtsoft.growtopia.Main`.
- Full rename dengan LIEF dan patch `com.rtsoft.` berjalan.

## 4. Scope

In scope:

- Import satu file `.xapk` atau `.apk` per proses.
- Diagnostik: package, version, min dan target SDK, daftar split, ABI, density, bahasa, OBB, ukuran, dan jumlah kemunculan package lama.
- Merge split di dalam satu XAPK menjadi standalone APK.
- Sanitasi atribut split pada manifest.
- Full rename applicationId, package Java, direktori smali, nama komponen, manifest, resource XML, asset teks, string native, dan simbol JNI.
- Ganti nama launcher dan icon aplikasi secara opsional. Nama menjadi label application dan launcher activity. Icon digenerate ke `mipmap-mdpi` sampai `mipmap-xxxhdpi` dan direferensikan sebagai `@mipmap/cloneclient_icon`.
- Ganti endpoint server native `www.growtopia1.com` dan `www.growtopia2.com` secara opsional. Kedua nilai harus tepat 18 karakter.
- Patch string native hanya jika panjang baru sama persis dengan panjang lama, sehingga offset ELF tidak berubah.
- Rebuild, zipalign, dan sign dengan release keystore.
- Output APK dan laporan proses.

Out of scope:

- Build dari source.
- Menggabungkan beberapa XAPK contoh menjadi satu universal APK.
- Embed OBB.
- Migrasi data pengguna dari path package lama ke path package baru.
- Mengubah logika game atau server di luar penggantian endpoint host.
- Hosting atau distribusi APK.

## 5. Pipeline

1. Validasi input, baca `manifest.json` pada XAPK, dan inventaris split.
2. Tampilkan diagnostik dan occurrence report.
3. Merge split dengan APKEditor (`m -i <input> -o merged.apk`). APKEditor juga menghapus `splitTypes`, `requiredSplitTypes`, `isSplitRequired`, `res/xml/splits0.xml`, dan meta-data split.
4. Decode dengan apktool.
5. Full rename:
   - `apktool.yml`: set `renameManifestPackage` ke package baru.
   - `AndroidManifest.xml`: ganti semua package lama dan path lama, termasuk komponen, authorities, permission, `targetPackage`, dan `sharedUserId`.
   - Smali: rename direktori `com/rtsoft/growtopia` menjadi `com/dev_rt/growtopia`, lalu ganti semua referensi di package tree.
   - `res/` XML dan asset teks: ganti package lama.
   - `.so`: rename 32 simbol JNI dengan LIEF, lalu ganti string package penuh, path, potongan `com.rtsoft.`, dan path potongannya.
   - Jika Server 1 atau Server 2 diisi, ganti `www.growtopia1.com` atau `www.growtopia2.com` di semua native library yang memuatnya dengan nilai 18 karakter yang sama panjang.
6. Terapkan appearance opsional:
   - Tulis app name ke `android:label` application dan launcher activity/alias.
   - Generate icon PNG 48, 72, 96, 144, dan 192 px ke `res/mipmap-*`, lalu set `android:icon` dan `android:roundIcon` ke `@mipmap/cloneclient_icon`.
7. Rebuild dengan apktool, lalu sign dan zipalign dengan uber-apk-signer.
8. Verifikasi manifest, app name, icon, server endpoints, dex, dynamic symbol JNI, layout, dan signature. Install dan launch di device atau emulator.
9. Tulis output ke `output/<name>-<version>-dev.apk` plus log.

## 6. Architecture

- GUI: PySide6, memakai fondasi CloneClient yang sudah ada.
- Layer:
  - `domain/`: `ApkInfo`, `SplitInfo`, `RenamePlan`, `PatchReport`, `VerificationReport`, dan aturan endpoint server.
  - `services/`: `InspectService` dan `RepackService`.
  - `infrastructure/`: adapter APKEditor, apktool, uber-apk-signer, LIEF JNI renamer, parser manifest, appearance/icon generator, native patcher, keystore, dan verifier.
  - `ui/`: `RepackagerView`, worker thread, dan tab Diagnostics/Repackager.
- Runtime Java: Temurin 21 minimal via `jlink` (`java.base,java.desktop,java.logging`, sekitar 46 MB) berisi `java` dan `keytool`, dibundel di dalam exe.
- Tool eksternal: `APKEditor.jar` 1.4.9, `apktool.jar` 3.0.3, dan `uber-apk-signer.jar` 1.3.0, semuanya dibundel.
- Dependency Python: `pyaxmlparser` untuk manifest, `lief` untuk ELF symbol table, dan `Pillow` untuk validasi serta resizing icon.
- Keystore release dibuat dengan `keytool`, disimpan di `%LOCALAPPDATA%\cloneclient\keystore`, password minimal 6 karakter, diminta saat proses dan tidak pernah ditulis ke log.

## 7. Aturan penggantian

- Package lama: `com.rtsoft.growtopia` (20 karakter), path `com/rtsoft/growtopia`, JNI `Java_com_rtsoft_growtopia_`, potongan `com.rtsoft.`.
- Package baru: `com.dev_rt.growtopia` (20 karakter), path `com/dev_rt/growtopia`, JNI `Java_com_dev_1rt_growtopia_`, potongan `com.dev_rt.`.
- Yang diubah: applicationId, package Java, direktori smali, nama class, nama komponen manifest, authorities, permission dinamis, resource XML, asset teks, string native, dan simbol JNI.
- Endpoint server native: `www.growtopia1.com` dan `www.growtopia2.com` (masing-masing 18 karakter). Pengganti harus 18 karakter, ASCII, tanpa spasi.
- String native hanya diganti jika panjang baru sama persis dengan panjang lama. Tidak ada padding dan tidak ada pergeseran offset.
- Simbol JNI diganti dengan LIEF agar dynamic symbol table dan GNU hash ikut diperbarui.
- Dynamic symbol JNI lama harus 0 dan dynamic symbol JNI baru harus ada. String literal JNI lama di `.rodata` boleh tersisa karena bukan symbol lookup.
- Hapus signature lama sebelum re-sign.
- Data pengguna di path package lama tidak dimigrasikan ke path baru.

## 8. GUI

- Tab Repack sebagai tab utama, Diagnostics sebagai tab sekunder.
- Input satu `.xapk` atau `.apk`, inspeksi otomatis setelah file dipilih atau di-drop, plus tombol Refresh info.
- Ringkasan package: version, SDK, ABI, density, bahasa, OBB, dan warning data lama.
- Appearance card opsional: app name dan file icon, preview icon 64 px, serta tombol Clear.
- Server endpoints card opsional: Server 1 dan Server 2, masing-masing tepat 18 karakter.
- Validasi inline: application id harus sama panjang dengan package lama, app name tidak boleh diawali `@` atau `?`, icon harus PNG/JPG/WebP minimal 48x48, endpoint server tepat 18 karakter, dan keystore password minimal 6 karakter.
- Blockers card hanya menampilkan requirement yang belum terpenuhi.
- Footer berisi satu primary action: Repack APK, Try again, atau Repack another, plus Cancel selama proses.
- Progress card hanya muncul saat run dan menampilkan tahap Merge, Decode, Rename, Appearance, Rebuild, Sign, Verify.
- Result card berisi Open folder, Copy path, dan status hasil.
- Report dan log disembunyikan dan dibuka lewat Show details.
- Keyboard: `Ctrl+O` pilih file, `Ctrl+R` repack, `Esc` cancel.
- Proses berjalan di worker thread agar UI tetap responsif.

## 9. Acceptance criteria

- [ ] GUI menerima satu `.xapk` atau `.apk` dan menampilkan diagnostik.
- [ ] Split XAPK berhasil menjadi standalone APK yang bisa di-install.
- [ ] Manifest `package`, komponen, authorities, dan permission memakai `com.dev_rt.growtopia`.
- [ ] Tidak ada referensi package lama di `AndroidManifest.xml` dan `classes*.dex`.
- [ ] Tidak ada string package penuh, path, atau potongan `com.rtsoft.` di `libgrowtopia.so`.
- [ ] Dynamic symbol JNI lama 0 dan dynamic symbol JNI baru minimal 32 untuk `libgrowtopia.so`.
- [ ] Package baru divalidasi harus sama persis panjangnya dengan package lama; selisih panjang ditolak sebelum proses.
- [ ] Patch `.so` tidak mengubah offset karena panjang string baru sama persis dengan yang lama.
- [ ] Keystore password minimal 6 karakter; input dan service menolak password lebih pendek sebelum proses berjalan.
- [ ] Output ditandatangani dengan release keystore, signature dan zipalign lolos verifikasi.
- [ ] App launch di device, `Main` resumed, SurfaceView render, dan crash buffer kosong.
- [ ] Data path baru mengikuti applicationId baru; data lama tidak otomatis dimigrasikan.
- [ ] Laporan memuat diagnostik, jumlah patch, warning, dan path output.
- [ ] Kegagalan tidak merusak input dan selalu menulis log.
- [ ] Exe berjalan di Windows x64 tanpa JDK host; `--tool-check` dan repack memakai runtime Temurin yang dibundel.
- [ ] App name opsional mengganti label application dan launcher activity/alias.
- [ ] Icon opsional menghasilkan lima PNG mipmap dan mengarahkan `android:icon` serta `android:roundIcon` ke resource baru.
- [ ] Verifier memeriksa app name dan icon output jika fitur tersebut dipilih.
- [ ] Server 1 dan Server 2 ditolak jika panjangnya bukan 18 karakter.
- [ ] Jika endpoint server diisi, string lama tidak tersisa dan string baru ada di native library.
- [ ] Verifier memeriksa server endpoint output jika fitur tersebut dipilih.

## 10. Verification

- Unit test untuk model, perencanaan rename, endpoint server, native patcher, rename engine, appearance/icon, verifier appearance/server, inspector, process runner, dan settings.
- Integration test keystore dengan `keytool`.
- Slow test end-to-end dengan XAPK contoh: merge, decode, full rename, app name/icon, server endpoints, build, sign, dan verify.
- Verifikasi manifest dengan `pyaxmlparser`, scan dex, cek dynamic JNI dengan LIEF, cek layout, dan verifikasi signature.
- CLI `--tool-check` dan `--inspect` untuk verifikasi headless.
- Uji exe di Windows VM bersih tanpa JDK: `--tool-check`, `--smoke`, `--inspect`, dan repack memakai runtime bundel.
- Install dan launch smoke test di device.
- Cek aturan Android 11+: `AndroidManifest.xml`, `resources.arsc`, dan `.so` tidak dikompresi serta 4-byte aligned.

## 11. Constraints dan risks

- ApplicationId valid: minimal dua segmen, tiap segmen diawali huruf, hanya huruf, angka, atau underscore. Hyphen tidak valid.
- Panjang package penuh dan potongan package baru harus sama persis dengan yang lama untuk patch native in-place. Package default 20 karakter penuh dan 11 karakter potongan.
- Keystore password minimal 6 karakter, mengikuti batas `keytool`.
- App name ditulis sebagai label literal; nilai yang diawali `@` atau `?` ditolak karena aapt akan membacanya sebagai resource reference.
- Icon menerima PNG, JPG, atau WebP minimal 48x48, di-center-crop, lalu di-resize ke 48, 72, 96, 144, dan 192 px. Icon lama dan adaptive XML lama tetap ada tetapi tidak dirujuk manifest baru.
- Server 1 dan Server 2 harus tepat 18 karakter, ASCII, tanpa spasi. Nilai kosong berarti endpoint lama dipertahankan.
- Simbol JNI tidak boleh diganti dengan byte replace; harus lewat LIEF agar hash ELF valid.
- Re-sign mengubah signature: user harus uninstall app lama, dan Play Protect atau SmartScreen bisa memberi warning.
- Tiga XAPK contoh adalah varian arsitektur berbeda. Tool memproses satu input per run, bukan merge lintas XAPK.
- Tidak ada OBB di XAPK contoh. Jika OBB ditemukan, tool memberi warning.
- Data pengguna lama tidak dimigrasikan. Path baru adalah `Android/data/com.dev_rt.growtopia`.
- Operator harus punya hak untuk memodifikasi dan mendistribusikan APK. Tool tidak memberi hak tersebut.
- APK hasil repack bisa ditandai antivirus atau SmartScreen.
- Runtime Temurin 21 minimal (sekitar 46.5 MB) dan JAR dibundel serta diverifikasi hash-nya. Exe onefile sekitar 122 MB dan mengekstrak runtime ke temp saat launch; build memerlukan network, runtime tidak.
- Server-side integrity atau perubahan anti-tamper di masa depan di luar scope tool.

## 12. Open material decisions

Sudah diputuskan:

- JAR dan runtime Temurin 21 (`jlink`, modul `java.base,java.desktop,java.logging`) dibundel dan diverifikasi; exe tidak membutuhkan JDK host.
- Keystore release digenerate dengan `keytool`; password minimal 6 karakter, diminta saat proses dan tidak disimpan.
- Format input: `.xapk` dan `.apk`.
- Bahasa UI: English.
- Sertifikat: RSA 2048, validity 10000 hari, alias `cloneclient`, CN `CloneClient`.
- OBB: beri warning lalu lanjut.
- Full rename Java, manifest, resource, native string, dan JNI symbol via LIEF.
- Endpoint server native diganti in-place hanya jika nilainya tepat 18 karakter; nilai kosong mempertahankan endpoint asli.
- Package baru `com.dev_rt.growtopia` (20 karakter) dan potongan `com.dev_rt.` (11 karakter).
- App name dan icon opsional. Label ditulis literal ke application/launcher; icon baru memakai resource `cloneclient_icon` di lima density dan `android:roundIcon` yang sama.

Masih terbuka:

- Migrasi data pengguna lama ke path package baru.
- Dukungan `.apks` atau `.apkm`.
- Penanganan server-side integrity di masa depan.

## 13. Boundaries

- **Always:** validasi input, tampilkan diagnostik, full rename, cek dynamic symbol JNI, scan dex, verifikasi signature, dan tulis log.
- **Ask first:** ganti tool eksternal, ubah aturan patch native, dan signing dengan keystore baru.
- **Never:** commit APK hasil atau keystore, memproses input tanpa diagnostik, dan mengklaim berhasil tanpa verifikasi.

## 14. Referensi

- APKEditor: https://github.com/reandroid/apkeditor
- xapk2apk: https://github.com/northlion/xapk2apk
- merge-apks: https://github.com/LuigiVampa92/merge-apks
- apktool rename package: https://stackoverflow.com/questions/36807634/changing-the-package-name
- Android applicationId rules: https://developer.android.com/build/configure-app-module
- Android manifest package: https://developer.android.com/guide/topics/manifest/manifest-element
- LIEF: https://lief.re/
- Repack dan signing reference: https://git.nite07.com/nite/apk-reverse/src/branch/main/skills/apk-reverse/references/repack-and-sign.md
