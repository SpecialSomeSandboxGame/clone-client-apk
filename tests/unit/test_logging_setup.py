import logging
import sys

from cloneclient.infrastructure.logging_setup import install_exception_hook


def test_exception_hook_logs_and_notifies(caplog) -> None:
    logger = logging.getLogger("cloneclient.test.crash")
    messages: list[str] = []
    original = sys.excepthook
    try:
        install_exception_hook(logger, messages.append)
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
    finally:
        sys.excepthook = original

    assert any("Unhandled exception" in record.getMessage() for record in caplog.records)
    assert messages
    assert "RuntimeError: boom" in messages[0]
