"""Levels + Brightness + Unsharp Mask + контроль яркости лица."""

from PIL import Image, ImageEnhance, ImageFilter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def apply_levels(img_gray, brightness_factor):
    """Применить Levels (brightness adjustment).

    Args:
        img_gray: PIL.Image в режиме L
        brightness_factor: множитель яркости (1.0 = нейтрально)

    Returns:
        PIL.Image: скорректированное изображение
    """
    enhancer = ImageEnhance.Brightness(img_gray)
    return enhancer.enhance(brightness_factor)


def apply_unsharp_mask(img, radius=1.5, percent=120, threshold=0):
    """Применить Unsharp Mask.

    Args:
        img: PIL.Image (grayscale)
        radius: радиус размытия
        percent: сила эффекта
        threshold: порог

    Returns:
        PIL.Image: обработанное изображение
    """
    return img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))


def check_face_brightness(img_gray, face_target, subject_mask):
    """Проверить и скорректировать яркость лица для ЧПУ.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        face_target: [min, max] целевого диапазона яркости
        subject_mask: PIL.Image в режиме L (маска субъекта)

    Returns:
        PIL.Image: скорректированное изображение
    """
    if HAS_NUMPY:
        arr = np.array(img_gray, dtype=np.float32)
        mask_arr = np.array(subject_mask)
        subject_pixels = arr[mask_arr > 128]
        if len(subject_pixels) == 0:
            return img_gray
        avg_brightness = float(subject_pixels.mean())
    else:
        from PIL import ImageStat
        stat = ImageStat.Stat(img_gray, mask=subject_mask)
        avg_brightness = stat.mean[0]

    target_min, target_max = face_target
    target_mid = (target_min + target_max) / 2

    if avg_brightness < target_min or avg_brightness > target_max:
        correction = target_mid / max(avg_brightness, 1)
        correction = max(0.85, min(1.25, correction))
        if HAS_NUMPY:
            arr = np.clip(arr * correction, 0, 255).astype(np.uint8)
            result = Image.fromarray(arr, "L")
        else:
            enhancer = ImageEnhance.Brightness(img_gray)
            result = enhancer.enhance(correction)
        print(f"Face brightness corrected: {avg_brightness:.0f} → "
              f"{target_mid:.0f} (factor: {correction:.3f})")
        return result

    print(f"Face brightness OK: {avg_brightness:.0f} (target: {target_min}-{target_max})")
    return img_gray
