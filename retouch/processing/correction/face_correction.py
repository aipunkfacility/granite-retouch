"""Face Brightness Correction — deprecated wrapper for face_brightness_correction.

Оставляет _curves_correction и _shrink_mask для обратной совместимости.
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


def _shrink_mask(subject_mask, shrink_px):
    """Сжать маску — убрать крайние shrink_px пикселей.

    Это исключает зону inner glow из замера яркости лица.
    Glow-пиксели (255) на контуре завышают среднее.
    """
    if HAS_NUMPY:
        from scipy.ndimage import gaussian_filter
        arr_float = (np.array(subject_mask) > 128).astype(np.float32)
        inv = 1.0 - arr_float
        blurred = gaussian_filter(inv, sigma=shrink_px)
        eroded = blurred < 0.1587
        return Image.fromarray(eroded.astype(np.uint8) * 255)
    else:
        from PIL import ImageOps, ImageFilter
        inv = ImageOps.invert(subject_mask)
        blurred = inv.filter(ImageFilter.GaussianBlur(radius=shrink_px))
        return blurred.point(lambda p, _t=40: 255 if p < _t else 0, "L")


def _curves_correction(arr, correction, highlight_start=200.0, mask=None,
                       target_ceiling=None):
    """Нелинейная коррекция: тени поднимаются, света не трогаются."""
    norm = arr / 255.0
    h = highlight_start / 255.0
    weight = np.where(
        norm < h,
        1.0,
        np.clip(1.0 - (norm - h) / (1.0 - h), 0, 1)
    )
    linear = arr * correction
    delta = linear - arr
    result = arr + delta * weight

    if target_ceiling is not None and correction > 1.0:
        proposed_delta = delta * weight
        max_allowed = np.maximum(target_ceiling - arr, 0)
        ceiling_scale = np.where(
            proposed_delta > 0,
            np.minimum(max_allowed / np.maximum(proposed_delta, 0.001), 1.0),
            1.0,
        )
        result = arr + proposed_delta * ceiling_scale

    if mask is not None:
        if mask.dtype == bool:
            result = np.where(mask, result, arr)
        else:
            alpha = mask.astype(np.float32)
            result = arr + (result - arr) * alpha

    return np.clip(result, 0, 255)


def check_face_brightness(img_gray, face_target, subject_mask, glow_size=0,
                          face_region_top=0.45, highlight_start=160,
                          white_ceiling=None, face_mask_img=None,
                          skin_threshold=100):
    """Deprecated wrapper. Используйте face_brightness_correction.

    Строит face_skin_mask из legacy параметров и делегирует
    в unified face_brightness_correction.
    """
    if not HAS_NUMPY:
        return _pillow_fallback(img_gray, face_target, subject_mask)

    arr = np.array(img_gray, dtype=np.float32)
    full_arr = np.array(subject_mask) > 128

    # Строим маску зоны лица из legacy параметров
    if glow_size > 0:
        inner_mask_img = _shrink_mask(subject_mask, glow_size)
        inner_arr = np.array(inner_mask_img) > 128
    else:
        inner_arr = full_arr

    if face_mask_img is not None:
        face_arr = np.array(face_mask_img) > 128
        face_mask = face_arr & inner_arr
        if not face_mask.any():
            face_mask = face_arr
        if not face_mask.any():
            face_mask = full_arr
    else:
        h = img_gray.height
        cutoff = int(h * face_region_top)
        face_mask = inner_arr.copy()
        face_mask[cutoff:, :] = False  # keep only top cutoff rows

    if not face_mask.any():
        return img_gray, 0.0, 0.0, 1.0, 0.0

    # Skin threshold filter
    if skin_threshold > 0:
        skin_mask = face_mask & (arr >= skin_threshold)
        if skin_mask.any():
            face_mask = skin_mask
        else:
            logger.info("Skin threshold %d: no pixels above, fallback to full face", skin_threshold)

    median_before = float(np.median(arr[face_mask]))
    p90 = float(np.percentile(arr[face_mask], 90))
    analytics = {"median_brightness": median_before, "p90_brightness": p90}

    cfg = {
        "face_brightness_target_min": face_target[0],
        "face_brightness_target_max": face_target[1],
        "white_ceiling": white_ceiling or 255,
        "rolloff_compression": 0.35,
    }

    result, before, after, factor, delta = face_brightness_correction(
        img_gray, subject_mask,
        face_mask.astype(np.uint8) * 255,
        cfg, analytics,
    )
    return result, before, after, factor, delta


def _pillow_fallback(img_gray, face_target, subject_mask):
    """Pillow fallback для случая без numpy."""
    from PIL import ImageStat
    stat = ImageStat.Stat(img_gray, mask=subject_mask)
    avg = stat.mean[0]
    target_min, target_max = face_target
    target_mid = (target_min + target_max) / 2

    if avg > target_max:
        factor = target_mid / max(avg, 1)
        factor = max(0.70, min(1.00, factor))
    elif avg < target_min:
        factor = min(1.15, 1.0 + min(target_min - avg, 15.0) / max(avg, 1))
    else:
        return img_gray, float(avg), float(avg), 1.0, 0.0

    enhancer = ImageEnhance.Brightness(img_gray)
    result = enhancer.enhance(factor)
    return result, float(avg), float(avg * factor), float(factor), 0.0
