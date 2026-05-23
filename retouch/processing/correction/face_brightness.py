"""Unified face brightness correction — linear shift + curves fine-tune.

Решает проблему двойной коррекции (levels + face_correction с разными масками):
1. Замер по face_skin (исключая волосы/бороду)
2. Linear shift: bounded delta ±15, shadow-priority weight (1 - norm^0.5)
3. Re-measure + curves fine-tune если median ещё вне target

Rolloff НЕ применяется в этом модуле — postprocess.py делает rolloff
после gamma, когда известны реальные значения пикселей.
Применение rolloff до gamma некорректно и вызывает двойной rolloff на highlights.

Note: параметр zone_masks deprecated и игнорируется.
"""

import logging

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from retouch.processing.correction.mask_utils import apply_masked

logger = logging.getLogger(__name__)

# Safety margin: face_skin must stay at least this many levels BELOW the
# rolloff knee after gamma is applied.  Without this margin, face_skin
# reaches exactly knee — any slight overshoot from unsharp or rounding
# pushes it into the rolloff zone, compressing tonal variation (gray plateau).
# MUST match the constant in steps.py safety cap.
FACE_SKIN_KNEE_MARGIN = 10


def _compute_gamma_aware_target(
    target_min: int,
    target_max: int,
    machine_cfg: dict,
) -> tuple[float, float]:
    """Compute effective target range adjusted for stone_gamma.

    When gamma < 1.0, pixel values are raised after face_brightness_correction.
    This function computes pre-gamma targets so that after gamma, the output
    stays safely below the rolloff knee (by FACE_SKIN_KNEE_MARGIN levels).

    The safety cap (Level 2) is applied in steps.py AFTER unsharp mask and
    BEFORE postprocess, using the same FACE_SKIN_KNEE_MARGIN constant.

    Args:
        target_min: original target minimum (e.g. 200 for impact)
        target_max: original target maximum (e.g. 225 for impact)
        machine_cfg: dict with stone_gamma, white_ceiling

    Returns:
        (effective_min, effective_max):
            effective_min: adjusted target_min for Phase 1/2
            effective_max: adjusted target_max for Phase 1/2
    """
    gamma = machine_cfg.get("stone_gamma", 1.0)

    if gamma is None or gamma >= 1.0:
        return float(target_min), float(target_max)

    ceiling = float(machine_cfg.get("white_ceiling", 250))
    knee = ceiling * 0.90

    # Maximum pre-gamma value so that after gamma, face_skin stays
    # at most (knee - FACE_SKIN_KNEE_MARGIN).  This prevents face_skin
    # from entering the rolloff compression zone.
    safe_post_gamma = knee - FACE_SKIN_KNEE_MARGIN
    max_pre_gamma = np.power(safe_post_gamma / 255.0, 1.0 / gamma) * 255.0

    # Pre-gamma values that produce target_min/target_max after gamma
    pre_gamma_min = np.power(target_min / 255.0, 1.0 / gamma) * 255.0
    pre_gamma_max = np.power(target_max / 255.0, 1.0 / gamma) * 255.0

    # Preserve target range width when targets exceed max_pre_gamma.
    # Naive clamping collapses effective_min == effective_max when both
    # targets are above the gamma-safe ceiling (laser presets: 230/245 with gamma 0.88).
    # Instead, shift the range down so effective_max = max_pre_gamma
    # and effective_min preserves the original range width.
    if pre_gamma_max > max_pre_gamma:
        original_width = pre_gamma_max - pre_gamma_min
        effective_max = max_pre_gamma
        # Shift down, preserving width — but don't go below 0
        effective_min = max(0.0, max_pre_gamma - original_width)
    else:
        effective_max = pre_gamma_max
        if pre_gamma_min > max_pre_gamma:
            # edge case: min above ceiling but max isn't — clamp min
            effective_min = max_pre_gamma
        else:
            effective_min = pre_gamma_min

    logger.info(
        "Gamma-aware target: gamma=%.2f, knee=%.1f, margin=%d, "
        "safe_post_gamma=%.1f, max_pre_gamma=%.1f, "
        "target_min=%d→effective_min=%.1f, target_max=%d→effective_max=%.1f",
        gamma, knee, FACE_SKIN_KNEE_MARGIN,
        safe_post_gamma, max_pre_gamma,
        target_min, effective_min,
        target_max, effective_max,
    )

    return effective_min, effective_max


def face_brightness_correction(
    img_gray: Image.Image,
    subject_mask: Image.Image,
    face_skin_mask: np.ndarray | None,
    machine_cfg: dict,
    analytics: dict,
    zone_masks=None,  # deprecated: не используется, rolloff перенесён в postprocess
    face_brightness_target_min: int = 180,
    face_brightness_target_max: int = 220,
    highlight_start: int = 200,
    max_delta: float = 15.0,
) -> tuple[Image.Image, float, float, float, float]:
    """Единая коррекция яркости лица.

    Args:
        img_gray: PIL.Image (L) — grayscale изображение
        subject_mask: PIL.Image (L) — маска субъекта
        face_skin_mask: numpy array или None — зона кожи лица (из ZoneMasks)
        machine_cfg: dict — параметры станка (face_brightness_target_min/max,
            white_ceiling, rolloff_compression)
        analytics: dict — метрики от analyze_input()
        zone_masks: ZoneMasks или None — DEPRECATED, игнорируется.
            Rolloff перенесён в postprocess.py. Параметр оставлен для
            обратной совместимости — будет удалён в будущей версии.
        face_brightness_target_min/max: fallback target range
        highlight_start: порог затухания curves (0-255)
        max_delta: максимальная дельта (safety envelope)
        variance_loss_threshold: порог клиппинга variance loss в %

    Returns:
        tuple: (Image, brightness_before, brightness_after, correction_factor, face_brightness_delta)
    """
    arr = np.array(img_gray, dtype=np.float32)
    subj_bool = np.array(subject_mask) > 128

    # Deprecation warning
    if zone_masks is not None:
        logger.warning(
            "face_brightness_correction: zone_masks parameter is deprecated "
            "and ignored. Rolloff is now handled by postprocess.py after gamma. "
            "Remove zone_masks from call sites."
        )

    # Определяем маску применения — face_skin с защитой субъекта
    if face_skin_mask is not None:
        if face_skin_mask.max() <= 1:
            skin_bool = face_skin_mask.astype(bool)
        else:
            skin_bool = face_skin_mask > 128
        apply_mask = subj_bool & skin_bool
    else:
        apply_mask = subj_bool

    if not apply_mask.any():
        logger.info("Face brightness: empty apply mask — no correction")
        return img_gray, 0.0, 0.0, 1.0, 0.0

    # --- Phase 1: Linear shift ---
    target_min = machine_cfg.get("face_brightness_target_min", face_brightness_target_min)
    target_max = machine_cfg.get("face_brightness_target_max", face_brightness_target_max)

    effective_min, effective_max = _compute_gamma_aware_target(
        target_min, target_max, machine_cfg,
    )
    target_mid = (effective_min + effective_max) / 2

    median_before = float(np.median(arr[apply_mask]))

    delta = 0.0
    if median_before < effective_min:
        delta = min(effective_min - median_before, max_delta)
    elif median_before > effective_max:
        delta = max(effective_max - median_before, -max_delta)

    corrected = arr.copy()
    if delta != 0:
        norm = arr / 255.0
        weight = 1.0 - np.power(norm, 0.5)
        corrected[apply_mask] = arr[apply_mask] + delta * weight[apply_mask]

    median_after_linear = float(np.median(corrected[apply_mask]))

    # --- Phase 2: Curves fine-tune ---
    correction = 1.0
    if median_after_linear < effective_min:
        delta2 = min(effective_min - median_after_linear, max_delta / 2)
        correction = (median_after_linear + delta2) / max(median_after_linear, 1)
        correction = max(1.0, min(1.10, correction))
    elif median_after_linear > effective_max:
        correction = target_mid / max(median_after_linear, 1)
        correction = max(0.85, min(1.00, correction))

    if correction != 1.0:
        h = highlight_start / 255.0
        norm_full = corrected / 255.0
        shadow_weight = 1.0 - np.power(norm_full, 0.5)
        highlight_taper = np.clip(1.0 - (norm_full - h) / (1.0 - h), 0, 1)
        weight_curve = np.where(
            norm_full < h,
            shadow_weight,
            highlight_taper,
        )
        linear = corrected * correction
        delta_curve = linear - corrected

        feather_radius = 10
        soft_mask_float = gaussian_filter(apply_mask.astype(np.float32), sigma=feather_radius)
        soft_mask = np.clip(soft_mask_float * subj_bool.astype(np.float32), 0, 1)

        corrected = corrected + delta_curve * weight_curve * soft_mask

    result_arr = apply_masked(arr, corrected, subject_mask)
    result_img = Image.fromarray(result_arr.astype(np.uint8))

    median_after = float(np.median(result_arr[apply_mask]))

    logger.info(
        "Face brightness: %.1f -> linear %.1f -> final %.1f "
        "(delta=%.1f, curves=%.3f, target=[%d,%d], effective=[%.1f,%.1f])",
        median_before, median_after_linear, median_after,
        delta, correction, target_min, target_max, effective_min, effective_max,
    )

    return result_img, median_before, median_after, correction, delta
