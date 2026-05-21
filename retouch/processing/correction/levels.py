"""Levels — коррекция яркости (bounded delta, зональная).

Этап 3: Заменён factor на ограниченную дельту с явным target range.
Вместо arr * factor используется двусторонняя формула:
  if median < target_min: delta = min(target_min - median, max_delta)
  elif median > target_max: delta = max(target_max - median, -max_delta)
  else: delta = 0

Delta применяется только к face_skin с весом от яркости.
"""

import logging

from PIL import Image, ImageEnhance

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)

from retouch.processing.correction.mask_utils import apply_masked as _apply_masked
from retouch.processing.correction.rolloff import soft_rolloff_masked


# ─── Levels — основная функция ────────────────────────────────────────

def apply_levels(img_gray, brightness_factor=None, analytics=None, machine_type=None,
                 subject_mask=None, machine_cfg=None, face_skin_mask=None, zone_masks=None):
    """Применить Levels (bounded delta correction).

    Этап 3: Вместо factor — двусторонняя bounded delta формула.
    Delta применяется только к face_skin (или subject_mask если face_skin_mask=None).

    Args:
        img_gray: PIL.Image в режиме L
        brightness_factor: legacy — множитель яркости (игнорируется если analytics)
        analytics: dict от analyze_input() — включает адаптивный расчёт
        machine_type: тип станка
        subject_mask: PIL.Image — маска субъекта
        machine_cfg: dict — параметры станка
        face_skin_mask: numpy array или None — маска кожи лица для зональной коррекции.
            Если None, коррекция применяется ко всей subject_mask (fallback).
        zone_masks: ZoneMasks или None — если предоставлен, rolloff использует highlights зону

    Returns:
        PIL.Image: скорректированное изображение
    """
    if analytics is not None and machine_type is not None:
        delta = _compute_bounded_delta(analytics, machine_type, machine_cfg)
    elif brightness_factor is not None:
        delta = (brightness_factor - 1.0) * 128.0
    else:
        delta = 0.0

    if delta == 0.0:
        return img_gray

    if subject_mask is not None and HAS_NUMPY:
        arr = np.array(img_gray, dtype=np.float32)
        subj_mask = np.array(subject_mask) > 128

        if face_skin_mask is not None:
            # Convert to boolean: handle both 0/1 uint8 and 0/255 masks
            if hasattr(face_skin_mask, 'max') and face_skin_mask.max() <= 1:
                face_skin_bool = face_skin_mask.astype(bool)
            else:
                face_skin_bool = face_skin_mask > 128
            apply_mask = subj_mask & face_skin_bool
        else:
            apply_mask = subj_mask

        if not apply_mask.any():
            return img_gray

        # Кривая с сохранением теней: weight=norm^0.5
        norm = arr / 255.0
        weight = np.power(norm, 0.5)

        # Применяем delta с весом
        corrected = arr.copy()
        corrected[apply_mask] = arr[apply_mask] + delta * weight[apply_mask]

        logger.info(
            "Levels applied: delta=%.1f, apply_mask_pixels=%d, corrected_median=%.1f",
            delta, apply_mask.sum(), np.median(corrected[apply_mask]),
        )

        # Soft knee ceiling via unified helper
        ceiling = 255.0
        if machine_cfg:
            ceiling = float(machine_cfg.get("white_ceiling", 255))
        compression = machine_cfg.get("rolloff_compression", 0.35) if machine_cfg else 0.35
        # v6.5: rolloff по highlights (если ZoneMasks доступен), иначе face_skin, иначе subject_mask
        if zone_masks is not None and zone_masks.highlights is not None and zone_masks.highlights.any():
            rolloff_mask_arr = (zone_masks.highlights > 128).astype(np.uint8) * 255
        elif face_skin_mask is not None:
            rolloff_mask_arr = face_skin_bool.astype(np.uint8) * 255
        else:
            rolloff_mask_arr = np.array(subject_mask, dtype=np.uint8)
        corrected = soft_rolloff_masked(corrected, rolloff_mask_arr, ceiling * 0.90, ceiling, compression)

        result_arr = _apply_masked(arr, corrected, subject_mask)
        return Image.fromarray(result_arr.astype(np.uint8))
    elif subject_mask is not None and not HAS_NUMPY:
        logger.warning(
            "apply_levels: subject_mask передана, но numpy недоступен — "
            "коррекция применяется глобально."
        )
        factor = 1.0 + delta / 128.0
        enhancer = ImageEnhance.Brightness(img_gray)
        return enhancer.enhance(factor)
    else:
        factor = 1.0 + delta / 128.0
        enhancer = ImageEnhance.Brightness(img_gray)
        return enhancer.enhance(factor)


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
