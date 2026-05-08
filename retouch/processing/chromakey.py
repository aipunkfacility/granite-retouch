"""Удаление синего хромакея + fringe removal."""

from PIL import Image

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def remove_blue_background(img, threshold=30, fringe_radius=3):
    """Удалить синий хромакей и убрать синие рефлексы (fringe) по краям.

    Использует numpy для скорости (~50x быстрее Pillow для 2048x2048).
    Fallback на Pillow при отсутствии numpy.

    Args:
        img: PIL.Image в режиме RGBA
        threshold: порог для определения синего хромакея
        fringe_radius: радиус расширения маски для fringe removal (px)

    Returns:
        tuple: (img_without_bg, subject_mask) — оба PIL.Image
    """
    if HAS_NUMPY:
        return _remove_blue_numpy(img, threshold, fringe_radius)
    return _remove_blue_pillow(img, threshold, fringe_radius)


def _remove_blue_numpy(img, threshold=30, fringe_radius=3):
    """numpy-реализация: удаление хромакея + fringe removal."""
    arr = np.array(img, dtype=np.float32)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    blue_mask = (b > r + threshold) & (b > g + threshold)

    if fringe_radius > 0:
        from scipy.ndimage import binary_dilation
        expanded_mask = binary_dilation(blue_mask, iterations=fringe_radius)
    else:
        expanded_mask = blue_mask

    fringe_zone = expanded_mask & ~blue_mask
    blue_strength = np.clip((b - np.maximum(r, g)) / (threshold * 2), 0, 1)
    fringe_factor = fringe_zone.astype(np.float32) * blue_strength
    arr[..., 2] = arr[..., 2] * (1 - fringe_factor) + np.maximum(r, g) * fringe_factor

    arr[blue_mask] = [0, 0, 0, 0]
    subject_arr = (~blue_mask).astype(np.uint8) * 255

    return Image.fromarray(arr.astype(np.uint8)), Image.fromarray(subject_arr)


def _remove_blue_pillow(img, threshold=30, fringe_radius=3):
    """Pillow-fallback: удаление хромакея + упрощённый fringe removal."""
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
