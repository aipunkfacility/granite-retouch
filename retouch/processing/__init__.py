"""Модуль обработки изображений granite-retouch."""

from .pipeline import process, process_steps, process_preview, process_export, PipelineResult, PipelineContext
from .export import export_result, save_bmp_8bit, save_bmp_1bit
from .levels import apply_levels
from .shadow_noise import add_shadow_noise
from .unsharp import apply_unsharp_mask
from .face_correction import check_face_brightness
from .face_region import detect_face_oval, generate_face_mask, generate_hair_mask
from .analysis import ImageAnalytics
from .zones import ZoneMasks, build_zone_masks, resolve_zone_priority
from .plan import PipelinePlan, ValidatedPlan, SafetyEnvelope, validate_plan
from .plan import PROFILE_PRESERVE, PROFILE_STANDARD, PROFILE_DIAGNOSTIC
from .metrics import ZoneMetrics, StepMetricsRecord, compute_zone_metrics, make_step_record
from .rolloff import soft_rolloff_masked
from .gates import GateState, GateResult
from .gates import (
    pre_check_face_dark_small,
    pre_check_contour_inner_quality,
    pre_check_skin_delta_envelope,
    post_check_variance_loss,
    post_check_clipped_pct,
    post_check_p95_shift,
    post_check_shadow_crush,
)

__all__ = [
    "process",
    "process_steps",
    "process_preview",
    "process_export",
    "PipelineResult",
    "PipelineContext",
    "export_result",
    "save_bmp_8bit",
    "save_bmp_1bit",
    "apply_levels",
    "add_shadow_noise",
    "apply_unsharp_mask",
    "check_face_brightness",
    "detect_face_oval",
    "generate_face_mask",
    "generate_hair_mask",
    "ImageAnalytics",
    "ZoneMasks",
    "build_zone_masks",
    "resolve_zone_priority",
    "PipelinePlan",
    "ValidatedPlan",
    "SafetyEnvelope",
    "validate_plan",
    "PROFILE_PRESERVE",
    "PROFILE_STANDARD",
    "PROFILE_DIAGNOSTIC",
    "ZoneMetrics",
    "StepMetricsRecord",
    "compute_zone_metrics",
    "make_step_record",
    "soft_rolloff_masked",
    "GateState",
    "GateResult",
    "pre_check_face_dark_small",
    "pre_check_contour_inner_quality",
    "pre_check_skin_delta_envelope",
    "post_check_variance_loss",
    "post_check_clipped_pct",
    "post_check_p95_shift",
    "post_check_shadow_crush",
]
