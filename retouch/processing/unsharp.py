"""Unsharp Mask — адаптивное повышение резкости."""

import logging

from PIL import Image, ImageFilter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from retouch.processing.mask_utils import apply_masked

logger = logging.getLogger(__name__)


def apply_unsharp_mask(img, radius=1.5, percent=120, threshold=0, subject_mask=None, analytics=None, white_ceiling=None):
    """Применить Unsharp Mask.

    Args:
        img: PIL.Image (grayscale)
        radius: радиус размытия
        percent: сила эффекта
        threshold: порог
        subject_mask: PIL.Image в режиме L — маска субъекта.
            Когда передана, резкость применяется только внутри маски (P6).
        analytics: dict от analyze_input() — если передан, включается
            адаптивный расчёт percent (P5).
        white_ceiling: int (0-255) — жёсткий потолок яркости. Unsharp может
            выталкивать светлые пиксели за ceiling, создавая клиппинг.
            Если передан, значения внутри subject_mask обрезаются до ceiling.

    Returns:
        PIL.Image: обработанное изображение
    """
    # P5: Адаптивный percent
    if analytics is not None:
        percent = _adaptive_unsharp_percent(analytics, percent)

    # Применяем Unsharp Mask
    sharpened = img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))

    # P6: Mask protection — резкость только внутри маски
    if subject_mask is not None and HAS_NUMPY:
        orig_arr = np.array(img, dtype=np.float32)
        sharp_arr = np.array(sharpened, dtype=np.float32)
        mask_bool = np.array(subject_mask) > 128
        result_arr = apply_masked(orig_arr, sharp_arr, subject_mask, mask_bool=mask_bool)

        # White ceiling: обрезаем значения внутри маски, чтобы unsharp
        # не вытолкнул пиксели за потолок яркости
        if white_ceiling is not None:
            result_arr[mask_bool] = np.minimum(result_arr[mask_bool], float(white_ceiling))
            logger.info("Unsharp white ceiling: %d", white_ceiling)

        return Image.fromarray(result_arr.astype(np.uint8))

    return sharpened


def _adaptive_unsharp_percent(analytics: dict, default_percent: int) -> int:
    """P5: Рассчитать адаптивный percent для Unsharp Mask.

    Args:
        analytics: dict с метриками от analyze_input()
        default_percent: значение по умолчанию (используется как fallback)

    Returns:
        int: адаптированный percent
    """
    tonal_range = analytics.get('tonal_range', 80)
    input_class = analytics.get('input_class', 'bright')

    if input_class == 'overbright':
        percent = 80
    elif tonal_range < 40:
        percent = 150
    elif tonal_range > 80:
        percent = 120
    else:
        percent = 130

    logger.info(
        "Adaptive unsharp: class=%s, tonal_range=%.1f, percent=%d",
        input_class, tonal_range, percent,
    )
    return percent
