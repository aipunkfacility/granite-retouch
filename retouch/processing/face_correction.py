"""Deprecated: use retouch.processing.correction.face_correction instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.face_correction' is deprecated. "
    f"Use 'retouch.processing.correction.face_correction' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.correction.face_correction import check_face_brightness, _curves_correction, _shrink_mask, HAS_NUMPY
