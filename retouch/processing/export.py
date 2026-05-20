"""Deprecated: use retouch.processing.output.export instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.export' is deprecated. "
    f"Use 'retouch.processing.output.export' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.output.export import export_result, save_bmp_8bit, save_bmp_1bit, HAS_NUMBA, jarvis_dither, stucki_dither, _error_diffusion_dither, _apply_dither
