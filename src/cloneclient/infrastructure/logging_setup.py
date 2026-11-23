"""Configure file logging and a global exception hook."""

from __future__ import annotations

import logging
import sys
import traceback
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from types import TracebackType

from cloneclient.infrastructure.paths import log_dir

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("cloneclient")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    handler = RotatingFileHandler(
        log_dir() / "cloneclient.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(handler)
    return logger


def install_exception_hook(
    logger: logging.Logger,
    notify: Callable[[str], None] | None = None,
) -> None:
    def handle(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logger.error("Unhandled exception", exc_info=(exc_type, exc, tb))
        if notify is not None:
            notify("".join(traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = handle
