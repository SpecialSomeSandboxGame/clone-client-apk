# Release

## Versioning

Follow semantic versioning. Update `pyproject.toml`, `build/version_info.txt`, and `CHANGELOG.md` in the same change.

## Continuous build

`.github/workflows/ci.yml` runs when `main` is pushed. It runs lint and tests, builds `dist/CloneClient.exe`, and uploads it as the `cloneclient-windows` workflow artifact. It does not create a tag or a GitHub Release.

## Checklist

1. Run the full verification in `docs/verification.md`.
2. Build `dist/CloneClient.exe` from a clean checkout. The build creates and bundles the minimal Temurin 21 runtime.
3. Run the executable on a machine without Python or Java. Confirm `--tool-check` points `java` and `keytool` at the extracted `runtime\bin` and that one repack succeeds.
4. Confirm the diagnostics view and clipboard action work.
5. Attach `CloneClient.exe`, `README.md`, `THIRD_PARTY_NOTICES.md`, and a SHA-256 file to the release.
6. Do not attach the keystore, XAPK, source tree, `.cache`, or output APKs.

## Code signing

Decision: code signing is deferred until after the 1.0 release. Builds are unsigned, so SmartScreen warns on first run. Enable signing only after a certificate is available, and update this document and `SPEC.md` when that happens.
