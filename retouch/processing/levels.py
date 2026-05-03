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


def _shrink_mask(subject_mask, shrink_px):
    """Сжать маску — убрать крайние shrink_px пикселей.

    Это исключает зону inner glow из замера яркости лица.
    Glow-пиксели (255) на контуре завышают среднее.
    """
    if HAS_NUMPY:
        from scipy.ndimage import binary_erosion
        arr = np.array(subject_mask) > 128
        eroded = binary_erosion(arr, iterations=shrink_px)
        return Image.fromarray((eroded.astype(np.uint8) * 255), "L")
    else:
        # Pillow fallback: invert → blur → threshold
        from PIL import ImageOps
        inv = ImageOps.invert(subject_mask)
        blurred = inv.filter(ImageFilter.GaussianBlur(radius=shrink_px))
        # Threshold at 128 — pixels near edge become 0 in mask
        return blurred.point(lambda p: 255 if p < 128 else 0, "L")


def _curves_correction(arr, correction):
    """Нелинейная коррекция: тени поднимаются, света не трогаются.

    Вместо linear brightness (всё × 1.15) — curves-подобная формула:
    - Тёмные пиксели (0) → полная коррекция
    - Средние пиксели (128) → 60% коррекции
    - Светлые пиксели (220+) → почти без коррекции

    Это поднимает лицо (тёмное) без пересвета воротника (светлого).
    """
    # Нормализуем в 0-1
    norm = arr / 255.0

    # Weight: 1.0 для теней, 0.0 для светов
    # Пиксель 0 → weight 1.0, пиксель 200 → weight ~0.2, пиксель 240+ → weight 0
    highlight_start = 200.0 / 255.0  # выше этого — снижаем коррекцию
    weight = np.where(
        norm < highlight_start,
        1.0,
        np.clip(1.0 - (norm - highlight_start) / (1.0 - highlight_start), 0, 1)
    )

    # Линейная коррекция: pixel * correction
    linear = arr * correction

    # Разница: насколько линейная коррекция меняет пиксель
    delta = linear - arr

    # Применяем delta с weight — тени полностью, света минимально
    result = arr + delta * weight

    return np.clip(result, 0, 255)


def check_face_brightness(img_gray, face_target, subject_mask, glow_size=0):
    """Проверить и скорректировать яркость лица для ЧПУ.

    Использует НЕлинейную (curves) коррекцию:
    - Тёмные области (лицо) корректируются полностью
    - Светлые области (воротник) почти не трогаются

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        face_target: [min, max] целевого диапазона яркости
        subject_mask: PIL.Image в режиме L (маска субъекта)
        glow_size: размер inner glow — на столько пикселей сжимаем маску

    Returns:
        PIL.Image: скорректированное изображение
    """
    # Сжать маску чтобы исключить glow-зону из замера
    if glow_size > 0:
        inner_mask = _shrink_mask(subject_mask, glow_size)
    else:
        inner_mask = subject_mask

    if HAS_NUMPY:
        arr = np.array(img_gray, dtype=np.float32)
        mask_arr = np.array(inner_mask)
        inner_pixels = arr[mask_arr > 128]
        if len(inner_pixels) == 0:
            inner_pixels = arr[np.array(subject_mask) > 128]
        if len(inner_pixels) == 0:
            return img_gray
        avg_brightness = float(inner_pixels.mean())
    else:
        from PIL import ImageStat
        stat = ImageStat.Stat(img_gray, mask=inner_mask)
        avg_brightness = stat.mean[0]

    target_min, target_max = face_target
    target_mid = (target_min + target_max) / 2

    print(f"Face brightness: {avg_brightness:.0f} (target: {target_min}-{target_max}, "
          f"glow_excluded: {glow_size}px)")

    if avg_brightness < target_min or avg_brightness > target_max:
        correction = target_mid / max(avg_brightness, 1)
        correction = max(0.60, min(1.40, correction))

        if HAS_NUMPY:
            # Нелинейная коррекция: тени поднимаются, света нет
            result_arr = _curves_correction(arr, correction)
            result = Image.fromarray(result_arr.astype(np.uint8), "L")
        else:
            # Pillow fallback — простая линейная коррекция (хуже, но работает)
            enhancer = ImageEnhance.Brightness(img_gray)
            result = enhancer.enhance(correction)

        # Проверяем результат на внутренней маске
        if HAS_NUMPY:
            result_arr = np.array(result, dtype=np.float32)
            new_avg = float(result_arr[mask_arr > 128].mean())
            print(f"  → corrected: {avg_brightness:.0f} → {new_avg:.0f} "
                  f"(factor: {correction:.3f}, curves)")
        else:
            print(f"  → corrected: {avg_brightness:.0f} → {target_mid:.0f} "
                  f"(factor: {correction:.3f}, linear)")
        return result

    print(f"  → OK, no correction needed")
    return img_gray
