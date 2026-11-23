"""Application identity and shared constants used across layers."""

APP_NAME = "CloneClient"
APP_ID = "cloneclient"

OLD_PACKAGE = "com.rtsoft.growtopia"
NEW_PACKAGE = "com.dev_rt.growtopia"
OLD_PACKAGE_PATH = "com/rtsoft/growtopia"
NEW_PACKAGE_PATH = "com/dev_rt/growtopia"
OLD_JNI_PREFIX = "Java_com_rtsoft_growtopia_"
NEW_JNI_PREFIX = "Java_com_dev_1rt_growtopia_"
OLD_PARTIAL_PREFIX = "com.rtsoft."
NEW_PARTIAL_PREFIX = "com.dev_rt."

DEFAULT_KEYSTORE_ALIAS = "cloneclient"
DEFAULT_KEYSTORE_FILENAME = "cloneclient-release.jks"
MIN_KEY_PASSWORD_LENGTH = 6
KEY_PASSWORD_MIN_MESSAGE = "Key password must be at least 6 characters"

TOOL_VERSIONS = {
    "APKEditor": "1.4.9",
    "apktool": "3.0.3",
    "uber-apk-signer": "1.3.0",
}
