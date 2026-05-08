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


# ─── Levels — основная функция ────────────────────────────────────────

def apply_levels(img_gray, brightness_factor=None, analytics=None, machine_type=None, subject_mask=None):
    """Применить Levels (brightness adjustment).

    Поддерживает два режима:
    - Legacy: positional brightness_factor, analytics=None → простой brightness enhance.
    - Adaptive: analytics provided → фактор вычисляется из метрик и machine_type.

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

    Returns:
        PIL.Image: скорректированное изображение
    """
    # Определяем фактор яркости
    if analytics is not None:
        # P2: Адаптивный расчёт фактора
        factor = _adaptive_levels_factor(analytics, machine_type)
    elif brightness_factor is not None:
        # Legacy: явный фактор
        factor = brightness_factor
    else:
        # Default: нейтральный
        factor = 1.0

    # Применяем коррекцию
    if subject_mask is not None and HAS_NUMPY:
        # P6: Mask protection — коррекция только внутри маски
        mask_bool = np.array(subject_mask) > 128
        arr = np.array(img_gray, dtype=np.float32)
        corrected = arr * factor
        corrected = np.clip(corrected, 0, 255)
        result_arr = np.where(mask_bool, corrected, arr)
        return Image.fromarray(result_arr.astype(np.uint8), "L")
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


def _adaptive_levels_factor(analytics: dict, machine_type: str | None) -> float:
    """P2: Рассчитать адаптивный фактор яркости на основе аналитики.

    ВАЖНО: target_pre_fb рассчитывается как "предварительная" яркость ПЕРЕД
    Face Brightness Correction. Поскольку check_face_brightness() уже поднимает
    яркость до целевого диапазона (230–245 / 190–210 / 200–225), Levels НЕ должен
    дублировать это осветление. Поэтому target_pre_fb устанавливается НИЖЕ
    целевого диапазона лица — Levels лишь "подтягивает" средние тона,
    а финальную настройку лица делает check_face_brightness().

    Args:
        analytics: dict с метриками от analyze_input()
        machine_type: тип станка

    Returns:
        float: множитель яркости
    """
    # target_pre_fb — целевая МЕДИАНА grayscale ПОСЛЕ Levels, ПЕРЕД Face Brightness.
    target_pre_fb = {
        'laser_standard': 180,   # face_target 230-245
        'laser_80w': 150,        # face_target 190-210
        'impact': 160,           # face_target 200-225
    }.get(machine_type, 160)

    median = analytics['median_brightness']
    factor = target_pre_fb / max(median, 1)
    factor = max(0.70, min(1.15, factor))

    # Защита от клиппинга: не выталкиваем p90 за white_ceiling
    white_ceiling = {
        'laser_standard': 250,
        'laser_80w': 235,
        'impact': 240,
    }.get(machine_type, 248)
    if analytics['p90_brightness'] * factor > white_ceiling:
        safe_factor = (white_ceiling - 2) / max(analytics['p90_brightness'], 1)
        factor = min(factor, safe_factor)

    logger.info(
        "Adaptive levels: machine=%s, median=%.1f, target=%d, factor=%.3f",
        machine_type, median, target_pre_fb, factor,
    )
    return factor
