# Pinned tools

The JAR files in this directory are downloaded by `scripts/fetch_tools.py` and
bundled into `dist/CloneClient.exe` by `build.py`. They are intentionally not
committed to version control.

| File | Version | Source |
| --- | --- | --- |
| `APKEditor.jar` | 1.4.9 | https://github.com/REAndroid/APKEditor |
| `apktool.jar` | 3.0.3 | https://github.com/iBotPeaches/Apktool |
| `uber-apk-signer.jar` | 1.3.0 | https://github.com/patrickfav/uber-apk-signer |

Run `uv run python scripts/fetch_tools.py` to verify or restore the files.
Java 17 or newer is required at runtime.
