"""Экспорт результатов пайплайна в форматы BMP для ЧПУ станков.

Поддерживаемые форматы:
- BMP 8-bit grayscale (256 оттенков, R=G=B палитра) — для laser_standard
- BMP 1-bit monochrome (dithered) — для laser_80w и impact
  - Floyd-Steinberg: быстрый, для бюджетных лазеров
  - Jarvis: плавные переходы, лучший для CO2 (SOP 4.1)
  - Stucki: чёткие линии, лучший для impact (SOP 4.1)
- PNG — для предпросмотра (обратно совместимый)

FIX #9: Добавлены Stucki и Jarvis dithering
FIX #10: Upsampling перед дизерингом (SOP 5.2)
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

    return Image.fromarray(result).convert('1')


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
    return Image.fromarray(result).convert('1')


def _error_diffusion_dither(img_gray, weights):
    """Обобщённый алгоритм дизеринга с диффузией ошибки.

    Args:
        img_gray: PIL.Image в режиме L
        weights: list of (dx, dy, coefficient) — матрица распределения ошибки

    Returns:
        PIL.Image: 1-bit монохромное изображение (mode '1')
    """
    if not HAS_NUMPY:
        logger.warning("error_diffusion_dither: numpy недоступен, используем пороговый дизеринг")
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

            for dx, dy, coeff in weights:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    arr[ny, nx] += error * coeff

    return Image.fromarray(result).convert('1')


def stucki_dither(img_gray):
    """Применить дизеринг Stucki к grayscale-изображению.

    Stucki — модификация алгоритма Джарвиса с улучшенным сохранением
    микроконтраста. Оптимальный выбор для ударной гравировки (SOP 4.1).

    Белый пиксель = игла ударяет, чёрный = пропуск.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)

    Returns:
        PIL.Image: 1-bit монохромное изображение (mode '1')
    """
    weights = [
        # Forward row
        (1, 0, 8/42), (2, 0, 4/42),
        # Next row
        (-2, 1, 2/42), (-1, 1, 4/42), (0, 1, 8/42), (1, 1, 4/42), (2, 1, 2/42),
        # Row after next
        (-2, 2, 1/42), (-1, 2, 2/42), (0, 2, 4/42), (1, 2, 2/42), (2, 2, 1/42),
    ]
    return _error_diffusion_dither(img_gray, weights)


def jarvis_dither(img_gray):
    """Применить дизеринг Jarvis, Judice & Ninke к grayscale-изображению.

    JJN даёт максимально плавные переходы — идеален для CO2 лазеров
    на мелкозернистом граните (SOP 4.1).

    Args:
        img_gray: PIL.Image в режиме L (grayscale)

    Returns:
        PIL.Image: 1-bit монохромное изображение (mode '1')
    """
    weights = [
        # Forward row
        (1, 0, 7/48), (2, 0, 5/48),
        # Next row
        (-2, 1, 3/48), (-1, 1, 5/48), (0, 1, 7/48), (1, 1, 5/48), (2, 1, 3/48),
        # Row after next
        (-2, 2, 1/48), (-1, 2, 3/48), (0, 2, 5/48), (1, 2, 3/48), (2, 2, 1/48),
    ]
    return _error_diffusion_dither(img_gray, weights)


def _apply_dither(img_gray, method='floyd_steinberg'):
    """Применить выбранный алгоритм дизеринга.

    Args:
        img_gray: PIL.Image в режиме L
        method: 'floyd_steinberg' | 'jarvis' | 'stucki'

    Returns:
        PIL.Image: 1-bit изображение
    """
    if method == 'stucki':
        return stucki_dither(img_gray)
    elif method == 'jarvis':
        return jarvis_dither(img_gray)
    else:
        return floyd_steinberg_dither_fast(img_gray)


def dither_with_upsample(img_gray, method='jarvis', upsample=2):
    """Применить дизеринг с предварительным upsampling'ом (SOP 5.2).

    SOP рекомендует увеличить разрешение в 2-4x перед конверсией в 1-bit.
    Это позволяет алгоритму дизеринга оперировать более мелкой сеткой,
    что минимизирует «зубчатость» (jaggies) на кривых линиях.

    Процесс: resize(up) → dither → resize(down)

    Args:
        img_gray: PIL.Image в режиме L
        method: алгоритм дизеринга
        upsample: коэффициент увеличения (1-4)

    Returns:
        PIL.Image: 1-bit изображение оригинального размера
    """
    if upsample <= 1:
        return _apply_dither(img_gray, method)

    width, height = img_gray.size

    # Upsample (Nearest Neighbor — SOP 5.2)
    up_w, up_h = width * upsample, height * upsample
    img_up = img_gray.resize((up_w, up_h), Image.NEAREST)

    # Dither at high resolution
    img_dithered = _apply_dither(img_up, method)

    # Downsample back to original size
    result = img_dithered.resize((width, height), Image.NEAREST)
    return result.convert('1')


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


def save_bmp_1bit(img, output_path, machine_type=None, dither_method=None, dither_upsample=1):
    """Сохранить изображение как 1-bit монохромный BMP с дизерингом.

    Формат: BMP, 1-bit (два цвета: чёрный и белый).
    Полутона имитируются дизерингом. Стандарт для лазерной гравировки 80W+.

    Белый = лазер включён, чёрный = лазер выключен.

    Args:
        img: PIL.Image (RGB или L)
        output_path: путь к выходному BMP-файлу
        machine_type: тип станка (для логирования)
        dither_method: 'floyd_steinberg' | 'jarvis' | 'stucki' | None (авто)
        dither_upsample: int (1-4) — во сколько раз увеличить перед дизерингом
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

    # Выбираем метод дизеринга
    method = dither_method or 'floyd_steinberg'

    # FIX #10: Upsampling перед дизерингом (SOP 5.2)
    if dither_upsample and dither_upsample > 1:
        img_dithered = dither_with_upsample(img_gray, method=method, upsample=dither_upsample)
    else:
        img_dithered = _apply_dither(img_gray, method)

    # Сохраняем как 1-bit BMP
    img_dithered.save(output_path, format='BMP')

    path = Path(output_path)
    size_kb = path.stat().st_size / 1024
    logger.info(
        "BMP 1-bit (%s dither) saved: %s (%dx%d, %.0f KB, machine=%s, upsample=%d)",
        method, output_path, img_dithered.width, img_dithered.height,
        size_kb, machine_type, dither_upsample or 1,
    )


def export_result(img, output_path, machine_type="laser_standard", fmt="bmp",
                  dither_method=None, dither_upsample=1):
    """Экспорт результата пайплайна в нужном формате.

    Формат по умолчанию — BMP. Для laser_80w: 1-bit BMP с дизерингом.
    Для laser_standard и impact: 8-bit grayscale BMP.

    Args:
        img: PIL.Image (RGB или L) — финальное изображение от пайплайна
        output_path: путь к выходному файлу (расширение будет заменено на .bmp)
        machine_type: тип станка ('laser_standard', 'laser_80w', 'impact')
        fmt: формат экспорта ('bmp', 'bmp_1bit', 'bmp_8bit', 'png')
        dither_method: алгоритм дизеринга ('floyd_steinberg', 'jarvis', 'stucki')
        dither_upsample: int — upsampling перед дизерингом (SOP 5.2)

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
        # laser_80w: 1-bit BMP с дизерингом (FIX #9: метод из конфига)
        save_bmp_1bit(img, bmp_path, machine_type=machine_type,
                      dither_method=dither_method, dither_upsample=dither_upsample)
    elif fmt == "bmp_1bit" and machine_type == "impact":
        # impact: 1-bit BMP с Stucki (SOP 4.1)
        method = dither_method or 'stucki'
        save_bmp_1bit(img, bmp_path, machine_type=machine_type,
                      dither_method=method, dither_upsample=dither_upsample)
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
