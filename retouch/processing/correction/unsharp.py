"""Unsharp Mask — адаптивное повышение резкости."""

import logging

from PIL import Image, ImageFilter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from retouch.processing.correction.mask_utils import apply_masked

logger = logging.getLogger(__name__)


def apply_unsharp_mask(img, radius=1.5, percent=120, threshold=0,
                        subject_mask=None, analytics=None, white_ceiling=None,
                        face_skin_mask=None, face_overshoot_limit=8):
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
        white_ceiling: DEPRECATED — ceiling обрабатывается в финальном
            postprocess через soft knee. Параметр сохранён для обратной
            совместимости сигнатуры, но игнорируется.
        face_skin_mask: numpy array — зона кожи лица (из ZoneMasks.face_skin).
            Если передана, overshoot на face_skin ограничивается до
            ±face_overshoot_limit уровней (amplitude cap).
            Может содержать значения 0/1 (boolean) или 0/255 (uint8).
        face_overshoot_limit: максимальный overshoot на face_skin (уровней).
            По умолчанию 8 — сохраняет текстуру, предотвращает засветку.

    Returns:
        PIL.Image: обработанное изображение
    """
    # P5: Адаптивный percent
    if analytics is not None:
        percent = _adaptive_unsharp_percent(analytics, percent)

    # Применяем Unsharp Mask
    sharpened = img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))

    # Если numpy не доступен — возвращаем как есть
    if not HAS_NUMPY:
        return sharpened

    # Если не нужна numpy-обработка — избегаем конверсии
    _needs_numpy = (subject_mask is not None
                    or (face_skin_mask is not None and face_overshoot_limit is not None))
    if not _needs_numpy:
        return sharpened

    orig_arr = np.array(img, dtype=np.float32)
    sharp_arr = np.array(sharpened, dtype=np.float32)

    # P1.1: face_skin overshoot protection (amplitude cap)
    if face_skin_mask is not None and face_overshoot_limit is not None:
        if face_skin_mask.max() <= 1:
            fs_bool = face_skin_mask.astype(bool)
        else:
            fs_bool = face_skin_mask > 128

        if fs_bool.any():
            delta_fs = sharp_arr[fs_bool] - orig_arr[fs_bool]
            clamped = np.clip(delta_fs, -face_overshoot_limit, face_overshoot_limit)
            sharp_arr[fs_bool] = orig_arr[fs_bool] + clamped

            _clamped_count = int(np.sum(np.abs(delta_fs) > face_overshoot_limit))
            if _clamped_count > 0:
                logger.info(
                    "Unsharp face_skin overshoot: %d pixels clamped "
                    "(amplitude limit=%d)",
                    _clamped_count, face_overshoot_limit,
                )

    # P6: Mask protection — резкость только внутри маски
    if subject_mask is not None:
        mask_bool = np.array(subject_mask) > 128
        result_arr = apply_masked(orig_arr, sharp_arr, subject_mask, mask_bool=mask_bool)
        return Image.fromarray(result_arr.astype(np.uint8))

    return Image.fromarray(sharp_arr.astype(np.uint8))


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
