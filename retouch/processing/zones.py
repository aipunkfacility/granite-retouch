"""Deprecated: use retouch.processing.analysis.zones instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.zones' is deprecated. "
    f"Use 'retouch.processing.analysis.zones' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.analysis.zones import ZoneMasks, build_zone_masks, resolve_zone_priority, _compute_adaptive_skin_threshold, _build_contour_masks, _morphological_contour
