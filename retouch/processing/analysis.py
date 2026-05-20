"""Deprecated: use retouch.processing.analysis.analysis instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.analysis' is deprecated. "
    f"Use 'retouch.processing.analysis.analysis' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.analysis.analysis import analyze_input, ImageAnalytics, ZoneAnalytics
