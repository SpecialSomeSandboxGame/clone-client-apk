"""Background worker so long Java operations never block the Qt event loop."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

from cloneclient.shared.errors import CancelledError

logger = logging.getLogger("cloneclient.ui.worker")

Progress = Callable[[int, str], None]
LogLine = Callable[[str], None]


class FunctionWorker(QThread):
    progress = Signal(int, str)
    log = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    canceled = Signal()

    def __init__(
        self,
        func: Callable[[Progress, LogLine], Any],
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._func = func

    def run(self) -> None:
        try:
            result = self._func(self.progress.emit, self.log.emit)
        except CancelledError:
            self.canceled.emit()
        except Exception as exc:
            logger.exception("background task failed")
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
