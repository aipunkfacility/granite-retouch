"""Levels — deprecated wrapper for face_brightness_correction.

v6.5: Вся логика brightness correction в face_brightness.py.
apply_levels остаётся как deprecated прокси для обратной совместимости.

* brightness_factor legacy path (без analytics): использует Pillow-enhance.
* Adaptive path (analytics + machine_type): делегирует в face_brightness_correction.
"""

import logging

from PIL import Image, ImageEnhance

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)

from retouch.processing.correction.face_brightness import face_brightness_correction
from retouch.processing.correction.unsharp import apply_unsharp_mask  # re-exported for backward compat
from retouch.processing.correction.face_correction import check_face_brightness  # re-exported for backward compat
from retouch.processing.correction.shadow_noise import add_shadow_noise  # re-exported for backward compat


# ─── Levels — deprecated wrapper ─────────────────────────────────────

def apply_levels(img_gray, brightness_factor=None, analytics=None, machine_type=None,
                 subject_mask=None, machine_cfg=None, face_skin_mask=None, zone_masks=None):
    """Deprecated. Используйте face_brightness_correction напрямую."""
    cfg = machine_cfg or {}
    an = analytics or {}

    if analytics is not None and machine_type is not None:
        target_min = _get_default_for_machine("face_brightness_target_min", machine_type, cfg.get("face_brightness_target_min", 180))
        target_max = _get_default_for_machine("face_brightness_target_max", machine_type, cfg.get("face_brightness_target_max", 220))
        delta = _compute_bounded_delta(an, machine_type, cfg)
        if delta == 0.0:
            return img_gray
        cfg["face_brightness_target_min"] = target_min
        cfg["face_brightness_target_max"] = target_max
        mask_pil = subject_mask if subject_mask is not None else Image.new("L", img_gray.size, 255)
        result, _, _, _, _ = face_brightness_correction(
            img_gray, mask_pil, face_skin_mask, cfg, an, zone_masks=zone_masks,
        )
        return result
    elif brightness_factor is not None:
        # Legacy: глобальный Pillow-enhance (brightness_factor path)
        if subject_mask is not None and HAS_NUMPY:
            arr = np.array(img_gray, dtype=np.float32)
            subj_bool = np.array(subject_mask) > 128
            median = float(np.median(arr[subj_bool])) if subj_bool.any() else 128.0
            delta = (brightness_factor - 1.0) * 128.0
            cfg["face_brightness_target_min"] = median + delta
            cfg["face_brightness_target_max"] = median + delta
            an = {"median_brightness": median, "p90_brightness": median + 20}
            result, _, _, _ = face_brightness_correction(
                img_gray, subject_mask, face_skin_mask, cfg, an, zone_masks=zone_masks,
            )
            return result
        enhancer = ImageEnhance.Brightness(img_gray)
        return enhancer.enhance(brightness_factor)
    else:
        return img_gray


def _compute_bounded_delta(analytics: dict, machine_type: str,
                           machine_cfg: dict | None = None) -> float:
    """Этап 3: Двусторонняя bounded delta формула.

    if median < target_min: delta = min(target_min - median, max_delta)
    elif median > target_max: delta = max(target_max - median, -max_delta)
    else: delta = 0

    max_delta ограничен safety envelope (±15 для face_skin).

    Args:
        analytics: dict с метриками от analyze_input()
        machine_type: тип станка
        machine_cfg: параметры станка

    Returns:
        float: delta в уровнях (0-255 шкала)
    """
    default_min = _get_default_for_machine("face_brightness_target_min", machine_type, 180)
    default_max = _get_default_for_machine("face_brightness_target_max", machine_type, 220)
    max_delta = 15.0  # safety envelope для face_skin

    target_min = default_min
    target_max = default_max
    if machine_cfg:
        target_min = machine_cfg.get("face_brightness_target_min", default_min)
        target_max = machine_cfg.get("face_brightness_target_max", default_max)

    median = analytics.get('median_brightness', 128.0)

    if median < target_min:
        target_delta = min(target_min - median, max_delta)
    elif median > target_max:
        target_delta = max(target_max - median, -max_delta)
    else:
        target_delta = 0.0

    logger.info(
        "Bounded delta: machine=%s, median=%.1f, target=[%d,%d], delta=%.1f",
        machine_type, median, target_min, target_max, target_delta,
    )
    return target_delta


def _get_default_for_machine(key: str, machine_type: str | None, fallback=160) -> int | float:
    """FIX-5: Получить значение из DEFAULTS для данного machine_type."""
    if machine_type is None:
        return fallback
    from retouch.config import DEFAULTS as _DEFAULTS
    mc = _DEFAULTS.get("processing", {}).get(machine_type, {})
    return mc.get(key, fallback)
