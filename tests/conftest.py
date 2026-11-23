import os

# The test suite must run on CI without a display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
