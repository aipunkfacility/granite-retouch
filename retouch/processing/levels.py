"""Levels — коррекция яркости (адаптивная и ручная).

F.1: Функции unsharp, face_correction, shadow_noise вынесены в отдельные
модули. Этот файл сохраняет backward-compatible re-exports для
существующего импорта: from retouch.processing.levels import check_face_brightness
"""

import logging

from PIL import Image, ImageEnhance

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


# ─── Backward-compatible re-exports (F.1) ──────────────────────────────

from retouch.processing.unsharp import apply_unsharp_mask, _adaptive_unsharp_percent
from retouch.processing.face_correction import (
    check_face_brightness,
    _curves_correction,
    _shrink_mask,
)
from retouch.processing.shadow_noise import add_shadow_noise
from retouch.processing.mask_utils import apply_masked


# ─── Levels — основная функция ────────────────────────────────────────

def apply_levels(img_gray, brightness_factor=None, analytics=None, machine_type=None, subject_mask=None, machine_cfg=None):
    """Применить Levels (brightness adjustment).

    Поддерживает два режима:
    - Legacy: positional brightness_factor, analytics=None → простой brightness enhance.
    - Adaptive: analytics provided → фактор вычисляется из метрик и machine_type.
      При наличии machine_cfg, адаптивный фактор умножается на brightness из конфига
      и white_ceiling читается из конфига вместо хардкода.

    Args:
        img_gray: PIL.Image в режиме L
        brightness_factor: множитель яркости (1.0 = нейтрально).
            Используется в legacy-режиме (когда analytics is None).
        analytics: dict от analyze_input() — если передан, включается
            адаптивный расчёт фактора (P2).
        machine_type: str — тип станка ('laser_standard', 'laser_80w', 'impact').
            Используется только вместе с analytics.
        subject_mask: PIL.Image в режиме L — маска субъекта.
            Когда передана, коррекция применяется только внутри маски (P6).
        machine_cfg: dict — параметры станка из config.yaml.
            Когда передан с analytics, brightness используется как корректирующий
            коэффициент, а white_ceiling — вместо хардкода.

    Returns:
        PIL.Image: скорректированное изображение
    """
    # Определяем фактор яркости
    if analytics is not None:
        # P2: Адаптивный расчёт фактора
        factor = _adaptive_levels_factor(analytics, machine_type, machine_cfg=machine_cfg)
    elif brightness_factor is not None:
        # Legacy: явный фактор
        factor = brightness_factor
    else:
        # Default: нейтральный
        factor = 1.0

    # Применяем коррекцию
    if subject_mask is not None and HAS_NUMPY:
        # P6: Mask protection — коррекция только внутри маски
        arr = np.array(img_gray, dtype=np.float32)
        corrected = arr * factor
        corrected = np.clip(corrected, 0, 255)
        result_arr = apply_masked(arr, corrected, subject_mask)
        return Image.fromarray(result_arr.astype(np.uint8))
    elif subject_mask is not None and not HAS_NUMPY:
        # Pillow fallback БЕЗ numpy — коррекция глобальная, но маска не применяется.
        logger.warning(
            "apply_levels: subject_mask передана, но numpy недоступен — "
            "коррекция применяется глобально (фон может загрязниться). "
            "Установите numpy: pip install numpy"
        )
        enhancer = ImageEnhance.Brightness(img_gray)
        return enhancer.enhance(factor)
    else:
        # Без маски — глобальная коррекция (старое поведение)
        enhancer = ImageEnhance.Brightness(img_gray)
        return enhancer.enhance(factor)


def _adaptive_levels_factor(analytics: dict, machine_type: str | None, machine_cfg: dict | None = None) -> float:
    """P2: Рассчитать адаптивный фактор яркости на основе аналитики.

    ВАЖНО: target_pre_fb рассчитывается как "предварительная" яркость ПЕРЕД
    Face Brightness Correction. Levels лишь "подтягивает" средние тона,
    а финальную настройку лица делает check_face_brightness().

    Когда передан machine_cfg:
    - brightness используется как корректирующий коэффициент (умножается на фактор)
    - white_ceiling читается из конфига вместо хардкода
    - target_pre_fb может быть переопределён через конфиг (ключ target_pre_fb)

    Args:
        analytics: dict с метриками от analyze_input()
        machine_type: тип станка
        machine_cfg: dict — параметры станка из config.yaml (опционально)

    Returns:
        float: множитель яркости
    """
    # target_pre_fb — целевая МЕДИАНА grayscale ПОСЛЕ Levels, ПЕРЕД Face Brightness.
    # Приоритет: machine_cfg > хардкод по machine_type
    hardcoded_pre_fb = {
        'laser_standard': 180,
        'laser_80w': 150,
        'impact': 160,
    }.get(machine_type, 160)

    target_pre_fb = hardcoded_pre_fb
    if machine_cfg:
        target_pre_fb = machine_cfg.get("target_pre_fb", hardcoded_pre_fb)

    median = analytics['median_brightness']
    factor = target_pre_fb / max(median, 1)
    # FIX #1: единый clamp, brightness убран (заменён на stone_gamma)
    factor = max(0.50, min(1.50, factor))

    # Защита от клиппинга: не выталкиваем p90 за white_ceiling
    # Приоритет: machine_cfg > хардкод по machine_type
    hardcoded_ceiling = {
        'laser_standard': 250,
        'laser_80w': 235,
        'impact': 240,
    }.get(machine_type, 248)

    white_ceiling = hardcoded_ceiling
    if machine_cfg:
        white_ceiling = machine_cfg.get("white_ceiling", hardcoded_ceiling)

    if analytics['p90_brightness'] * factor > white_ceiling:
        safe_factor = (white_ceiling - 2) / max(analytics['p90_brightness'], 1)
        factor = min(factor, safe_factor)

    logger.info(
        "Adaptive levels: machine=%s, median=%.1f, target=%d, factor=%.3f",
        machine_type, median, target_pre_fb, factor,
    )
    return factor
