"""Deprecated: use retouch.processing.correction.levels instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.levels' is deprecated. "
    f"Use 'retouch.processing.correction.levels' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.correction.levels import apply_levels, apply_unsharp_mask, check_face_brightness, _curves_correction, _shrink_mask, add_shadow_noise, apply_masked, soft_rolloff_masked, HAS_NUMPY, _adaptive_unsharp_percent
