"""Deprecated: use retouch.processing.correction.unsharp instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.unsharp' is deprecated. "
    f"Use 'retouch.processing.correction.unsharp' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.correction.unsharp import apply_unsharp_mask, _adaptive_unsharp_percent
