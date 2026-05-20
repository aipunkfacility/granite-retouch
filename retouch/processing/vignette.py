"""Deprecated: use retouch.processing.output.vignette instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.vignette' is deprecated. "
    f"Use 'retouch.processing.output.vignette' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.output.vignette import apply_vignette, generate_arch_mask
