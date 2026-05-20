"""Deprecated: use retouch.processing.correction.rolloff instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.rolloff' is deprecated. "
    f"Use 'retouch.processing.correction.rolloff' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.correction.rolloff import soft_rolloff_masked
