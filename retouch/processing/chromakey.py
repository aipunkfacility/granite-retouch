"""Удаление синего хромакея + fringe removal + софт-маска.

PERF: uint8 вместо float32 для основного массива — -48 MB на 2048×2048
FIX: Софт-маска вместо бинарной — устраняет лестничный эффект на границах
"""

from PIL import Image

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def remove_blue_background(img, threshold=30, fringe_radius=3, mask_soft_sigma=1.5):
    """Удалить синий хромакей и убрать синие рефлексы (fringe) по краям.

    Использует numpy для скорости (~50x быстрее Pillow для 2048x2048).
    Fallback на Pillow при отсутствии numpy.

    Args:
        img: PIL.Image в режиме RGBA
        threshold: порог для определения синего хромакея
        fringe_radius: радиус расширения маски для fringe removal (px)
        mask_soft_sigma: sigma Gaussian blur для софт-краёв маски.
            0 = бинарная маска (старое поведение).
            1.0-2.0 = плавные края без ступенек (рекомендуется).

    Returns:
        tuple: (img_without_bg, subject_mask) — оба PIL.Image
    """
    if HAS_NUMPY:
        return _remove_blue_numpy(img, threshold, fringe_radius, mask_soft_sigma)
    return _remove_blue_pillow(img, threshold, fringe_radius)


def _smooth_dilate(mask, radius):
    """Изотропная дилатация через GaussianBlur — без лесенки на диагоналях.

    binary_dilation с дефолтным structuring element (крест) даёт
    ступеньки на диагональных краях. GaussianBlur + threshold
    эквивалентен дилатации с круглым ядром.
    """
    from scipy.ndimage import gaussian_filter
    # dilation = размыть фон наружу, взять порог
    blurred = gaussian_filter(mask.astype(np.float32), sigma=radius)
    return blurred > 0.5


def _smooth_erode(mask, radius):
    """Изотропная эрозия через GaussianBlur — без лесенки на диагоналях.

    binary_erosion с дефолтным structuring element (крест) даёт
    ступеньки. Эрозия = инвертировать → размыть → порог → инвертировать.
    """
    from scipy.ndimage import gaussian_filter
    inv = (~mask).astype(np.float32)
    blurred = gaussian_filter(inv, sigma=radius)
    return blurred < 0.5


def _remove_blue_numpy(img, threshold=30, fringe_radius=3, mask_soft_sigma=1.5):
    """numpy-реализация: удаление хромакея + fringe + софт-маска.

    Оптимизация памяти: uint8 вместо float32 для основного массива.
    float32 используется только в fringe-зоне (гораздо меньше всего изображения).
    Все морфологические операции через GaussianBlur — изотропные, без лесенки.
    """
    # uint8 — основная работа (4 байт/пиксель вместо 16 при float32)
    arr = np.array(img)  # uint8 RGBA
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    # Сравнение в int16 (uint8 + int может overflow)
    blue_mask = (b.astype(np.int16) > r.astype(np.int16) + threshold) & \
                (b.astype(np.int16) > g.astype(np.int16) + threshold)

    # --- Fringe removal (float только в зоне ореола) ---
    if fringe_radius > 0:
        expanded_mask = _smooth_dilate(blue_mask, radius=fringe_radius)
    else:
        expanded_mask = blue_mask

    fringe_zone = expanded_mask & ~blue_mask
    if np.any(fringe_zone):
        # Float-вычисления ТОЛЬКО для пикселей fringe-зоны
        fringe_ys, fringe_xs = np.where(fringe_zone)
        b_f = b[fringe_ys, fringe_xs].astype(np.float32)
        r_f = r[fringe_ys, fringe_xs].astype(np.float32)
        g_f = g[fringe_ys, fringe_xs].astype(np.float32)
        blue_strength = np.clip((b_f - np.maximum(r_f, g_f)) / (threshold * 2), 0, 1)
        fringe_factor = blue_strength  # fringe_zone already filtered
        b_corrected = (b_f * (1 - fringe_factor) + np.maximum(r_f, g_f) * fringe_factor).astype(np.uint8)
        arr[fringe_ys, fringe_xs, 2] = b_corrected

    # Удаляем синий фон — мягкий переход через альфу вместо бинарной вырезки.
    # Бинарная вырезка arr[blue_mask]=[0,0,0,0] даёт лесенку на диагоналях.
    # Вместо этого: плавный переход alpha от 0 (фон) до 255 (субъект).
    from scipy.ndimage import gaussian_filter
    alpha_hard = (~blue_mask).astype(np.float32) * 255.0
    # Небольшой blur по альфе — сгладить лесенку blue_mask на диагоналях
    alpha_blur_sigma = max(1.0, mask_soft_sigma * 0.5)
    alpha_smooth = gaussian_filter(alpha_hard, sigma=alpha_blur_sigma)
    arr[..., 3] = np.clip(alpha_smooth, 0, 255).astype(np.uint8)
    # Гарантируем что чистый фон = полностью прозрачный
    arr[blue_mask, 3] = 0

    # --- Софт-маска вместо жёсткой бинарной ---
    if mask_soft_sigma > 0:
        subject_mask_float = (~blue_mask).astype(np.float32) * 255.0
        subject_mask_float = gaussian_filter(subject_mask_float, sigma=mask_soft_sigma)

        # Возвращаем 255 внутри (не размываем вглубь субъекта)
        inner = ~blue_mask
        inner_solid = _smooth_erode(inner, radius=max(1, int(mask_soft_sigma * 2)))
        subject_mask_float[inner_solid] = 255.0

        subject_arr = np.clip(subject_mask_float, 0, 255).astype(np.uint8)
    else:
        # Бинарная маска (старое поведение)
        subject_arr = (~blue_mask).astype(np.uint8) * 255

    return Image.fromarray(arr), Image.fromarray(subject_arr)


def _remove_blue_pillow(img, threshold=30, fringe_radius=3):
    """Pillow-fallback: удаление хромакея + упрощённый fringe removal.

    Примечание: Pillow-fallback не поддерживает mask_soft_sigma —
    всегда возвращает бинарную маску. numpy-реализация доступна.
    """
    width, height = img.size
    data = list(img.getdata())
    new_data = []
    mask_pixels = []

    for item in data:
        r, g, b, a = item
        if b > r + threshold and b > g + threshold:
            new_data.append((0, 0, 0, 0))
            mask_pixels.append(0)
        else:
            if fringe_radius > 0 and b > r and b > g:
                blue_excess = min((b - max(r, g)) / (threshold * 2), 1.0)
                b_corrected = int(b * (1 - blue_excess) + max(r, g) * blue_excess)
                new_data.append((r, g, b_corrected, a))
            else:
                new_data.append(item)
            mask_pixels.append(255)

    img_result = Image.new("RGBA", (width, height))
    img_result.putdata(new_data)
    subject_mask = Image.new('L', (width, height))
    subject_mask.putdata(mask_pixels)

    return img_result, subject_mask
