"""Collect runtime facts for the diagnostics view."""

from __future__ import annotations

import platform
import sys

from cloneclient import __version__
from cloneclient.domain.diagnostics import build_diagnostics
from cloneclient.infrastructure.paths import user_data_dir
from cloneclient.shared.constants import APP_NAME


def collect_diagnostics() -> str:
    values = {
        "Application": APP_NAME,
        "Version": __version__,
        "Python": platform.python_version(),
        "Implementation": platform.python_implementation(),
        "Operating system": platform.platform(),
        "Architecture": platform.machine(),
        "Executable": sys.executable,
        "Data directory": str(user_data_dir()),
    }
    return build_diagnostics(values)
