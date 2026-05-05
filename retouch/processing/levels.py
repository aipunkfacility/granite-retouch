"""Levels + Brightness + Unsharp Mask + контроль яркости лица."""

import logging

from PIL import Image, ImageEnhance, ImageFilter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


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


def _curves_correction(arr, correction, highlight_start=200.0):
    """Нелинейная коррекция: тени поднимаются, света не трогаются.

    Вместо linear brightness (всё × 1.15) — curves-подобная формула:
    - Тёмные пиксели (0) → полная коррекция
    - Средние пиксели (128) → 60% коррекции
    - Светлые пиксели (highlight_start+) → почти без коррекции

    Args:
        arr: numpy array (float32), значения 0-255
        correction: множитель коррекции (1.0 = нейтрально)
        highlight_start: значение (0-255), выше которого коррекция затухает
    """
    # Нормализуем в 0-1
    norm = arr / 255.0

    # Weight: 1.0 для теней, 0.0 для светов
    h = highlight_start / 255.0
    weight = np.where(
        norm < h,
        1.0,
        np.clip(1.0 - (norm - h) / (1.0 - h), 0, 1)
    )

    # Линейная коррекция: pixel * correction
    linear = arr * correction

    # Разница: насколько линейная коррекция меняет пиксель
    delta = linear - arr

    # Применяем delta с weight — тени полностью, света минимально
    result = arr + delta * weight

    return np.clip(result, 0, 255)


def check_face_brightness(img_gray, face_target, subject_mask, glow_size=0,
                          face_region_top=0.45, highlight_start=200):
    """Проверить и скорректировать яркость лица для ЧПУ.

    Использует НЕлинейную (curves) коррекцию:
    - Тёмные области (лицо) корректируются полностью
    - Светлые области (воротник) почти не трогаются

    Breaking Change: теперь возвращает кортеж (img, before, after, factor).
    Ранее возвращала только img.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        face_target: [min, max] целевого диапазона яркости
        subject_mask: PIL.Image в режиме L (маска субъекта)
        glow_size: размер inner glow — на столько пикселей сжимаем маску
        face_region_top: доля высоты изображения, в которой замеряется яркость.
            0.45 = верхние 45% картинки (голова без плеч).
        highlight_start: значение (0-255), выше которого коррекция затухает.
            Вынесено из хардкода 200 в параметр конфига.

    Returns:
        tuple: (img, before, after, factor) — скорректированное изображение,
               яркость до, яркость после, множитель коррекции.
    """
    # Сжать маску чтобы исключить glow-зону из замера
    if glow_size > 0:
        inner_mask_img = _shrink_mask(subject_mask, glow_size)
    else:
        inner_mask_img = subject_mask

    if HAS_NUMPY:
        arr = np.array(img_gray, dtype=np.float32)

        # A4: Правильная последовательность — сначала np.array от маски,
        # потом обрезка верхней части для зоны лица
        subject_mask_arr = np.array(subject_mask)
        mask_arr = np.array(inner_mask_img)

        # Ограничиваем зону замера верхней частью (лицо без плеч)
        h = img_gray.height
        cutoff = int(h * face_region_top)
        face_region = subject_mask_arr.copy()
        face_region[cutoff:, :] = 0  # Обнуляем нижнюю часть

        inner_mask = face_region > 128
        if inner_mask.sum() == 0:
            # fallback на полную маску (без обрезки по высоте)
            inner_mask = subject_mask_arr > 128

        inner_pixels = arr[inner_mask]
        if len(inner_pixels) == 0:
            # Нет пикселей субъекта — вернуть без изменений
            return img_gray, 0.0, 0.0, 1.0

        avg_brightness = float(inner_pixels.mean())
    else:
        from PIL import ImageStat
        stat = ImageStat.Stat(img_gray, mask=inner_mask_img)
        avg_brightness = stat.mean[0]
        # Без numpy face_region_top не применяется — fallback на полную маску

    target_min, target_max = face_target
    target_mid = (target_min + target_max) / 2

    logger.info("Face brightness: %.1f → target %d-%d", avg_brightness, target_min, target_max)

    if avg_brightness < target_min or avg_brightness > target_max:
        correction = target_mid / max(avg_brightness, 1)
        correction = max(0.60, min(1.40, correction))

        if HAS_NUMPY:
            # Нелинейная коррекция: тени поднимаются, света нет
            result_arr = _curves_correction(arr, correction, highlight_start=highlight_start)
            result = Image.fromarray(result_arr.astype(np.uint8), "L")
        else:
            # Pillow fallback — простая линейная коррекция (хуже, но работает)
            enhancer = ImageEnhance.Brightness(img_gray)
            result = enhancer.enhance(correction)

        # Проверяем результат на внутренней маске
        if HAS_NUMPY:
            result_arr_check = np.array(result, dtype=np.float32)
            new_avg = float(result_arr_check[inner_mask].mean())
            logger.info("Curves correction: factor=%.3f, %.1f → %.1f", correction, avg_brightness, new_avg)
        else:
            new_avg = target_mid
            logger.info("Linear correction: factor=%.3f, %.1f → %.1f", correction, avg_brightness, new_avg)

        return result, float(avg_brightness), float(new_avg), float(correction)

    logger.info("Face brightness OK, no correction needed")
    return img_gray, float(avg_brightness), float(avg_brightness), 1.0
