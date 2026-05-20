"""Deprecated: use retouch.processing.correction.mask_utils instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.mask_utils' is deprecated. "
    f"Use 'retouch.processing.correction.mask_utils' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.correction.mask_utils import apply_masked, clamp_masked
