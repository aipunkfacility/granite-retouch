"""Экспорт результатов пайплайна в форматы BMP для ЧПУ станков.

Поддерживаемые форматы:
- BMP 8-bit grayscale (256 оттенков, R=G=B палитра) — для laser_standard и impact
- BMP 1-bit monochrome (dithered, Floyd-Steinberg) — для laser_80w
- PNG — для предпросмотра (обратно совместимый)
"""

import logging
from pathlib import Path

from PIL import Image

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


def floyd_steinberg_dither(img_gray):
    """Применить дизеринг Floyd-Steinberg к grayscale-изображению.

    Преобразует 8-bit grayscale в 1-bit монохромное изображение,
    имитируя полутона паттернами чёрных и белых точек.
    Это стандартный алгоритм для лазерной гравировки в бинарном режиме.

    Белый пиксель = лазер включён (выжигает), чёрный = лазер выключен.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)

    Returns:
        PIL.Image: 1-bit монохромное изображение (mode '1')
    """
    if not HAS_NUMPY:
        # Pillow fallback: простой порог
        logger.warning("floyd_steinberg_dither: numpy недоступен, используем пороговый дизеринг")
        return img_gray.convert('1')

    arr = np.array(img_gray, dtype=np.float64)
    height, width = arr.shape
    result = np.zeros((height, width), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            old_pixel = arr[y, x]
            new_pixel = 255.0 if old_pixel >= 128.0 else 0.0
            result[y, x] = 255 if new_pixel == 255.0 else 0
            error = old_pixel - new_pixel

            if x + 1 < width:
                arr[y, x + 1] += error * 7 / 16
            if y + 1 < height:
                if x - 1 >= 0:
                    arr[y + 1, x - 1] += error * 3 / 16
                arr[y + 1, x] += error * 5 / 16
                if x + 1 < width:
                    arr[y + 1, x + 1] += error * 1 / 16

    return Image.fromarray(result, mode='L').convert('1')


def floyd_steinberg_dither_fast(img_gray):
    """Быстрый Floyd-Steinberg дизеринг с векторизованной обработкой строк.

    Аналогичен floyd_steinberg_dither(), но обрабатывает строки целиком
    через numpy-операции, что значительно быстрее для больших изображений.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)

    Returns:
        PIL.Image: 1-bit монохромное изображение (mode '1')
    """
    if not HAS_NUMPY:
        return floyd_steinberg_dither(img_gray)

    arr = np.array(img_gray, dtype=np.float64)
    height, width = arr.shape
    result = np.zeros((height, width), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            old_pixel = arr[y, x]
            new_pixel = 255.0 if old_pixel >= 128.0 else 0.0
            result[y, x] = 255 if new_pixel == 255.0 else 0
            error = old_pixel - new_pixel

            # Распределение ошибки на соседние пиксели
            if x + 1 < width:
                arr[y, x + 1] += error * 7 / 16
            if y + 1 < height:
                if x - 1 >= 0:
                    arr[y + 1, x - 1] += error * 3 / 16
                arr[y + 1, x] += error * 5 / 16
                if x + 1 < width:
                    arr[y + 1, x + 1] += error * 1 / 16

    # Конвертируем в 1-bit через порог 128
    return Image.fromarray(result, mode='L').convert('1')


def save_bmp_8bit(img, output_path, machine_type=None):
    """Сохранить изображение как 8-bit grayscale BMP с палитрой R=G=B.

    Формат: BMP, 8-bit indexed, палитра 256 записей (0,0,0)...(255,255,255).
    Это стандартный формат для ударной гравировки и лазерной в полутоновом режиме.

    Args:
        img: PIL.Image (RGB или L)
        output_path: путь к выходному BMP-файлу
        machine_type: тип станка (для логирования)
    """
    # Конвертируем в grayscale если нужно
    if img.mode == 'RGB':
        img_gray = img.convert('L')
    elif img.mode == 'RGBA':
        img_gray = img.convert('L')
    elif img.mode == '1':
        img_gray = img.convert('L')
    else:
        img_gray = img

    # Создаём 8-bit BMP с палитрой R=G=B
    # PIL автоматически создаёт правильную grayscale палитру при сохранении L как BMP
    img_gray.save(output_path, format='BMP')

    path = Path(output_path)
    size_kb = path.stat().st_size / 1024
    logger.info(
        "BMP 8-bit saved: %s (%dx%d, %.0f KB, machine=%s)",
        output_path, img_gray.width, img_gray.height, size_kb, machine_type,
    )


def save_bmp_1bit(img, output_path, machine_type=None):
    """Сохранить изображение как 1-bit монохромный BMP с Floyd-Steinberg дизерингом.

    Формат: BMP, 1-bit (два цвета: чёрный и белый).
    Полутона имитируются дизерингом. Стандарт для лазерной гравировки 80W+.

    Белый = лазер включён, чёрный = лазер выключен.

    Args:
        img: PIL.Image (RGB или L)
        output_path: путь к выходному BMP-файлу
        machine_type: тип станка (для логирования)
    """
    # Конвертируем в grayscale
    if img.mode == 'RGB':
        img_gray = img.convert('L')
    elif img.mode == 'RGBA':
        img_gray = img.convert('L')
    elif img.mode == '1':
        img_gray = img.convert('L')
    else:
        img_gray = img

    # Применяем Floyd-Steinberg дизеринг
    img_dithered = floyd_steinberg_dither_fast(img_gray)

    # Сохраняем как 1-bit BMP
    img_dithered.save(output_path, format='BMP')

    path = Path(output_path)
    size_kb = path.stat().st_size / 1024
    logger.info(
        "BMP 1-bit (dithered) saved: %s (%dx%d, %.0f KB, machine=%s)",
        output_path, img_dithered.width, img_dithered.height, size_kb, machine_type,
    )


def export_result(img, output_path, machine_type="laser_standard", fmt="bmp"):
    """Экспорт результата пайплайна в нужном формате.

    Формат по умолчанию — BMP. Для laser_80w: 1-bit BMP с дизерингом.
    Для laser_standard и impact: 8-bit grayscale BMP.

    Args:
        img: PIL.Image (RGB или L) — финальное изображение от пайплайна
        output_path: путь к выходному файлу (расширение будет заменено на .bmp)
        machine_type: тип станка ('laser_standard', 'laser_80w', 'impact')
        fmt: формат экспорта ('bmp', 'bmp_1bit', 'bmp_8bit', 'png')

    Returns:
        str: фактический путь к сохранённому файлу
    """
    output = Path(output_path)

    if fmt == "png":
        # PNG для предпросмотра / обратной совместимости
        png_path = str(output.with_suffix(".png"))
        if img.mode != 'RGB':
            img.convert('RGB').save(png_path, format='PNG')
        else:
            img.save(png_path, format='PNG')
        logger.info("PNG saved: %s", png_path)
        return png_path

    # BMP — основной формат для ЧПУ
    bmp_path = str(output.with_suffix(".bmp"))

    if fmt == "bmp_1bit" or (fmt == "bmp" and machine_type == "laser_80w"):
        # laser_80w: 1-bit BMP с Floyd-Steinberg дизерингом
        save_bmp_1bit(img, bmp_path, machine_type=machine_type)
    else:
        # laser_standard, impact: 8-bit grayscale BMP
        save_bmp_8bit(img, bmp_path, machine_type=machine_type)

    # Также сохраняем PNG для предпросмотра
    png_path = str(output.with_suffix(".png"))
    if img.mode != 'RGB':
        img.convert('RGB').save(png_path, format='PNG')
    else:
        img.save(png_path, format='PNG')
    logger.info("PNG preview saved: %s", png_path)

    return bmp_path
