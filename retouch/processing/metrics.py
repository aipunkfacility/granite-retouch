"""Deprecated: use retouch.processing.analysis.metrics instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.metrics' is deprecated. "
    f"Use 'retouch.processing.analysis.metrics' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.analysis.metrics import ZoneMetrics, StepMetricsRecord, compute_zone_metrics, make_step_record
