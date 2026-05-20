"""Deprecated: use retouch.processing.detection.chromakey instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.chromakey' is deprecated. "
    f"Use 'retouch.processing.detection.chromakey' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.detection.chromakey import remove_blue_background, _make_smooth_mask, _compute_blue_strength, HAS_CV2, HAS_SCIPY
