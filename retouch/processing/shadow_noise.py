"""Deprecated: use retouch.processing.correction.shadow_noise instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.shadow_noise' is deprecated. "
    f"Use 'retouch.processing.correction.shadow_noise' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.correction.shadow_noise import add_shadow_noise
