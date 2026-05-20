"""Deprecated: use retouch.processing.correction.gamma instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.gamma' is deprecated. "
    f"Use 'retouch.processing.correction.gamma' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.correction.gamma import apply_stone_gamma, apply_stone_gamma_masked
