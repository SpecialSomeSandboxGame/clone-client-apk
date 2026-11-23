# Changelog

## 0.5.0

- Added optional replacement for the `www.growtopia1.com` and `www.growtopia2.com` server hosts inside native libraries.
- Added Server 1 and Server 2 inputs with exact 18-character validation and inline errors.
- Native patching is length-preserving, so the ELF offsets and symbol tables stay intact.
- Added a server endpoints verification check and end-to-end coverage.

## 0.4.0

- Added optional launcher app name and icon replacement. The name is written to the application and launcher labels, and the icon is resized into five mipmap densities as `cloneclient_icon`.
- Added icon preview and validation in the Appearance card, plus inline app name and icon errors in the blockers card.
- Added an Appearance pipeline stage and output verification for the requested name and icon.
- Added Pillow for icon validation and resizing.
- Added unit, verifier, UI, and end-to-end tests for appearance changes.

## 0.3.0

- Bundled a pinned Temurin 21 Java runtime in the one-file executable, so users no longer install Java or download JAR files.
- Added a `jlink` runtime build step with a pinned JDK hash and the `java.base,java.desktop,java.logging` module set.
- The toolchain now prefers `runtime/bin/java.exe` and its sibling `keytool`, with the host JDK only as a fallback for source runs.
- Added exact package length validation and a minimum 6-character keystore password check before the pipeline starts.
- Added toolchain tests for the bundled runtime and keytool lookup.

## 0.2.0

- Added the XAPK/APK repackager: merge splits with APKEditor, full package rename, signing, and verification.
- Renamed Java classes, smali directories, manifest components, resource XML, native package strings, and the partial `com.rtsoft.` prefix.
- Added LIEF-based JNI symbol rewriting so the ELF dynamic symbol table and hash tables match the new package.
- Added dex, manifest, native dynamic symbol, layout, and signature verification before success is reported.
- Added the Repackager tab with a background worker, progress, diagnostics, and log.
- Added toolchain discovery, pinned JAR fetch with SHA-256 verification, and release keystore generation.
- Added `--tool-check` and `--inspect` CLI modes, with report files for windowed builds.
- Validated the full rename on a device: `Main` resumed, SurfaceView rendering, and an empty crash buffer.

## 0.1.0

- Added the desktop application foundation with a diagnostics view.
- Added logging, crash reporting, and per-user data paths.
- Added JSON settings persistence for window geometry and theme under `%LOCALAPPDATA%\cloneclient`.
- Added a controlled `--crash-test` path that verifies the crash handler and log output.
- Added the PyInstaller single-file Windows build pipeline.
- Added lint, format, style, import-boundary, and UI smoke tests.
