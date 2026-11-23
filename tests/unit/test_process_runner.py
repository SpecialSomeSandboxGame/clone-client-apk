import sys
import threading

import pytest

from cloneclient.infrastructure.process_runner import require_success, run_command
from cloneclient.shared.errors import CancelledError, ToolError


def test_run_command_captures_output() -> None:
    result = run_command([sys.executable, "-c", "print('hello')"])

    assert result.returncode == 0
    assert "hello" in result.output
    assert result.duration >= 0


def test_require_success_reports_tail() -> None:
    result = run_command([sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"])

    with pytest.raises(ToolError) as error:
        require_success(result, "demo")

    assert "exit code 3" in str(error.value)
    assert "bad" in str(error.value)


def test_run_command_times_out() -> None:
    with pytest.raises(ToolError):
        run_command([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.5)


def test_run_command_cancels() -> None:
    event = threading.Event()
    timer = threading.Timer(0.3, event.set)
    timer.daemon = True
    timer.start()

    with pytest.raises(CancelledError):
        run_command(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=10,
            cancel_event=event,
        )
    timer.cancel()
