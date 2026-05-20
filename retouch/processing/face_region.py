"""Deprecated: use retouch.processing.detection.face_region instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.face_region' is deprecated. "
    f"Use 'retouch.processing.detection.face_region' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.detection.face_region import detect_face_oval, generate_face_mask, generate_hair_mask, _detect_face_by_width_profile
