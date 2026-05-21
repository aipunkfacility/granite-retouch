"""Deprecated: use retouch.processing.core.pipeline instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.pipeline' is deprecated. "
    f"Use 'retouch.processing.core.pipeline' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.core.pipeline import process, process_steps, process_preview, process_export
from retouch.processing.core.context import PipelineResult, PipelineContext
