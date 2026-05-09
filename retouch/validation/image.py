"""Валидация входного изображения."""

import os


class ValidationError(Exception):
    """Ошибка валидации входных данных или результата."""
    pass


def validate_image_input(input_path, config=None):
    """Проверить, что входное изображение пригодно для обработки.

    Проверки:
    1. Файл существует
    2. Файл — изображение (Pillow может открыть)
    3. Разрешение >= min_resolution
    4. Разрешение <= max_resolution (защита от OOM)
    5. Формат RGBA-конвертируемый
    """
    from PIL import Image
    from retouch.config import DEFAULTS

    if config is None:
        config = DEFAULTS

    proc = config.get("processing", DEFAULTS["processing"])
    min_res = proc.get("min_resolution", 512)
    max_res = proc.get("max_resolution", None)

    if not os.path.isfile(input_path):
        raise ValidationError(f"Входной файл не найден: {input_path}")

    try:
        img = Image.open(input_path)
    except Exception as e:
        raise ValidationError(f"Не удалось открыть изображение: {e}")

    width, height = img.size
    if width < min_res or height < min_res:
        img.close()
        raise ValidationError(
            f"Разрешение {width}x{height} ниже минимума {min_res}x{min_res}. "
            f"Для качественной гравировки нужно изображение большего размера."
        )

    if max_res and (width > max_res or height > max_res):
        img.close()
        raise ValidationError(
            f"Разрешение {width}x{height} превышает максимум {max_res}x{max_res}. "
            f"Слишком большое изображение может вызвать нехватку памяти (OOM)."
        )

    if img.mode not in ("RGBA", "RGB", "P", "L"):
        img.close()
        raise ValidationError(
            f"Неподдерживаемый режим изображения: {img.mode}. "
            f"Ожидается RGBA, RGB или палитровое изображение."
        )

    img.close()
    return True


def validate_blue_chromakey(img, threshold=30, min_blue_ratio=0.15):
    """Проверить, что изображение содержит синий хромакей (#0000FF).

    Использует numpy при наличии (быстрее), иначе fallback на Pillow.
    """
    try:
        import numpy as np
        arr = np.array(img)
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        blue_mask = (b > r + threshold) & (b > g + threshold)
        ratio = float(blue_mask.sum()) / blue_mask.size
    except ImportError:
        data = list(img.getdata())
        total = len(data)
        blue_pixels = sum(1 for px in data if px[2] > px[0] + threshold and px[2] > px[1] + threshold)
        ratio = blue_pixels / total

    if ratio < min_blue_ratio:
        raise ValidationError(
            f"Синий хромакей не обнаружен (синих пикселей: {ratio:.1%}, "
            f"минимум: {min_blue_ratio:.0%}). "
            f"Ожидается изображение с фоном #0000FF."
        )

    return ratio


def validate_result_black_ratio(img, min_black_ratio=0.25):
    """Проверить, что результат содержит достаточно чёрного фона."""
    try:
        import numpy as np
        arr = np.array(img)
        black_mask = (arr[..., 0] < 10) & (arr[..., 1] < 10) & (arr[..., 2] < 10)
        ratio = float(black_mask.sum()) / black_mask.size
    except ImportError:
        data = list(img.getdata())
        total = len(data)
        black_pixels = sum(1 for r, g, b in data if r < 10 and g < 10 and b < 10)
        ratio = black_pixels / total

    if ratio < min_black_ratio:
        raise ValidationError(
            f"Недостаточно чёрного фона в результате ({ratio:.1%}, "
            f"минимум: {min_black_ratio:.0%}). "
            f"Возможно, хромакей не был удалён или виньетка не наложилась."
        )

    return ratio
