"""Deprecated: use retouch.processing.core.gates instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.gates' is deprecated. "
    f"Use 'retouch.processing.core.gates' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.core.gates import GateState, GateResult, pre_check_face_dark_small, pre_check_contour_inner_quality, pre_check_skin_delta_envelope, post_check_variance_loss, post_check_clipped_pct, post_check_p95_shift, post_check_shadow_crush
