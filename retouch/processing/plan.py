"""Deprecated: use retouch.processing.core.plan instead.

This module is a backward-compatibility shim. It will be removed in v7.0.
"""
import warnings

warnings.warn(
    "Module 'retouch.processing.plan' is deprecated. "
    f"Use 'retouch.processing.core.plan' instead. "
    "This module will be removed in v7.0.",
    DeprecationWarning,
    stacklevel=2,
)

from retouch.processing.core.plan import PipelinePlan, ValidatedPlan, SafetyEnvelope, validate_plan, PROFILE_PRESERVE, PROFILE_STANDARD, PROFILE_DIAGNOSTIC, VALID_PROFILES, PROFILE_ACTIVE_STEPS
