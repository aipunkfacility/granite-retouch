"""Экспорт результатов пайплайна в форматы BMP для ЧПУ станков.

Поддерживаемые форматы:
- BMP 8-bit grayscale (256 оттенков, R=G=B палитра) — для laser_standard
- BMP 1-bit monochrome (dithered) — для laser_80w
  - Jarvis: плавные переходы, лучший для CO2 (SOP 4.1)
- PNG — для предпросмотра (обратно совместимый)

Формат BMP выбирается по dither_method из конфига станка:
  - laser_standard: dither_method='none' → 8-bit grayscale
  - laser_80w: dither_method='jarvis' → 1-bit BMP с Jarvis dithering
  - impact: dither_method='none' → 8-bit grayscale (256 уровней силы удара)

FIX #9: Добавлены Stucki и Jarvis dithering
FIX #10: Upsampling перед дизерингом (SOP 5.2)
PERF: Numba @njit для дизеринга — 50-200x ускорение
BREAKING: Floyd-Steinberg удалён, floyd_steinberg редиректит на jarvis
"""

import logging
from pathlib import Path

from PIL import Image

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Numba JIT-ядро дизеринга
# ---------------------------------------------------------------------------

if HAS_NUMBA:
    @njit(cache=True)
    def _error_diffusion_dither_jit(arr_float, offsets_x, offsets_y, weights, n_weights):
        """Numba-ускоренный алгоритм дизеринга с диффузией ошибки.

        Работает in-place на arr_float (float64).
        Возвращает uint8-массив результата.
        """
        height, width = arr_float.shape
        result = np.empty((height, width), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                old_pixel = arr_float[y, x]
                new_pixel = 255.0 if old_pixel >= 128.0 else 0.0
                result[y, x] = 255 if new_pixel == 255.0 else 0
                error = old_pixel - new_pixel
                for i in range(n_weights):
                    nx = x + offsets_x[i]
                    ny = y + offsets_y[i]
                    if 0 <= nx < width and 0 <= ny < height:
                        arr_float[ny, nx] += error * weights[i]
        return result


def _error_diffusion_dither(img_gray, weights):
    """Обобщённый алгоритм дизеринга с диффузией ошибки.

    При наличии Numba использует JIT-компилированную версию
    (50-200x быстрее чистого Python). Fallback на Python при отсутствии Numba.

    Args:
        img_gray: PIL.Image в режиме L
        weights: list of (dx, dy, coefficient) — матрица распределения ошибки

    Returns:
        PIL.Image: 1-bit монохромное изображение (mode '1')
    """
    if not HAS_NUMPY:
        logger.warning("error_diffusion_dither: numpy недоступен, используем пороговый дизеринг")
        return img_gray.convert('1')

    if HAS_NUMBA:
        # Numba JIT path — подготовка плоских массивов
        arr_float = np.array(img_gray, dtype=np.float64)
        n_weights = len(weights)
        offsets_x = np.array([w[0] for w in weights], dtype=np.int64)
        offsets_y = np.array([w[1] for w in weights], dtype=np.int64)
        weights_arr = np.array([w[2] for w in weights], dtype=np.float64)

        result = _error_diffusion_dither_jit(
            arr_float, offsets_x, offsets_y, weights_arr, n_weights
        )
        return Image.fromarray(result).convert('1')

    # Python fallback — чистый Python без Numba
    arr = np.array(img_gray, dtype=np.float64)
    height, width = arr.shape
    pixel_count = height * width
    if pixel_count > 500_000:
        logger.warning(
            "Numba не установлена, дизеринг на чистом Python. "
            "Размер %dx%d (%d пикс.) — ожидайте 30-120 сек. "
            "Установите: uv sync --extra fast",
            width, height, pixel_count,
        )
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


def _apply_dither(img_gray, method='jarvis'):
    """Применить выбранный алгоритм дизеринга.

    Args:
        img_gray: PIL.Image в режиме L
        method: 'jarvis' | 'stucki' | 'floyd_steinberg' (deprecated → jarvis)

    Returns:
        PIL.Image: 1-bit изображение
    """
    if method == 'stucki':
        return stucki_dither(img_gray)
    else:
        # jarvis — default; floyd_steinberg редиректит сюда (deprecated)
        if method == 'floyd_steinberg':
            logger.info("floyd_steinberg deprecated, redirecting to jarvis")
        return jarvis_dither(img_gray)


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
        dither_method: 'jarvis' | 'stucki' | None (авто)
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
    method = dither_method or 'jarvis'

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
                  dither_method=None, dither_upsample=1, save_png_preview=False):
    """Экспорт результата пайплайна в нужном формате.

    Логика выбора формата:
    - fmt='png' → PNG (предпросмотр)
    - fmt='bmp_1bit' → 1-bit BMP с дизерингом (любой станок)
    - fmt='bmp' + dither_method != 'none' → 1-bit BMP с дизерингом из конфига
    - fmt='bmp' + dither_method == 'none' → 8-bit grayscale BMP

    Машины по умолчанию:
    - laser_standard: dither_method='none' → 8-bit grayscale
    - laser_80w: dither_method='jarvis' → 1-bit BMP с Jarvis dithering
    - impact: dither_method='none' → 8-bit grayscale (256 уровней силы удара)

    Args:
        img: PIL.Image (RGB или L) — финальное изображение от пайплайна
        output_path: путь к выходному файлу (расширение будет заменено на .bmp)
        machine_type: тип станка ('laser_standard', 'laser_80w', 'impact')
        fmt: формат экспорта ('bmp', 'bmp_1bit', 'bmp_8bit', 'png')
        dither_method: алгоритм дизеринга ('jarvis', 'stucki', 'floyd_steinberg' (deprecated), 'none')
            None = авто (из конфига станка)
        dither_upsample: int — upsampling перед дизерингом (SOP 5.2)
        save_png_preview: bool — сохранить PNG-дубликат рядом с BMP (по умолчанию False)

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

    if fmt == "bmp_8bit":
        # Явный запрос 8-bit grayscale
        save_bmp_8bit(img, bmp_path, machine_type=machine_type)
    elif fmt == "bmp_1bit":
        # Явный запрос 1-bit — дизеринг обязателен
        method = dither_method if dither_method and dither_method != "none" else "jarvis"
        save_bmp_1bit(img, bmp_path, machine_type=machine_type,
                      dither_method=method, dither_upsample=dither_upsample)
    elif fmt == "bmp" and dither_method and dither_method != "none":
        # Конфиг станка требует дизеринг → 1-bit BMP
        # laser_80w (jarvis), impact (stucki)
        save_bmp_1bit(img, bmp_path, machine_type=machine_type,
                      dither_method=dither_method, dither_upsample=dither_upsample)
    else:
        # fmt='bmp' + dither_method='none' → 8-bit grayscale
        # laser_standard
        save_bmp_8bit(img, bmp_path, machine_type=machine_type)

    # PNG preview — только по явному запросу (save_png_preview=True)
    if save_png_preview:
        png_path = str(output.with_suffix(".png"))
        if img.mode != 'RGB':
            img.convert('RGB').save(png_path, format='PNG')
        else:
            img.save(png_path, format='PNG')
        logger.info("PNG preview saved: %s", png_path)

    return bmp_path
