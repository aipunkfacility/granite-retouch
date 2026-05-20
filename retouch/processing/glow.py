"""Deprecated: use retouch.processing.correction.glow instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.glow' is deprecated. "
    f"Use 'retouch.processing.correction.glow' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.correction.glow import apply_glow, apply_outer_glow, apply_inner_glow, _calculate_glow_params, apply_inner_glow_algorithm, HAS_NUMPY
