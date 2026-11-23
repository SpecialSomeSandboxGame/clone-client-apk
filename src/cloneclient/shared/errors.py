"""Error types shared by the repackager pipeline."""

from __future__ import annotations


class CloneClientError(Exception):
    """Base class for errors that are safe to show to the operator."""


class InputError(CloneClientError):
    """The selected file cannot be processed."""


class ToolError(CloneClientError):
    """An external tool is missing or failed."""


class PipelineError(CloneClientError):
    """A pipeline stage produced an unusable result."""


class CancelledError(CloneClientError):
    """The operator canceled a running operation."""
