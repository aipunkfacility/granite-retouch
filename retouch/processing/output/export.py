"""Экспорт результатов пайплайна в форматы BMP для ЧПУ станков.

Поддерживаемые форматы:
- BMP 8-bit grayscale (256 оттенков, R=G=B палитра) — ПО УМОЛЧАНИЮ для всех машин
  - SAUNO Engrave: модулирует мощность лазера по яркости (алгоритмы Р1–Р5)
  - Ударные станки: 256 уровней силы удара
- BMP 1-bit monochrome (dithered) — опционально через export_mode='1bit'
  - Jarvis: плавные переходы, лучший для CO2 (SOP 4.1)
  - Stucki: улучшенный микроконтраст, для ударной гравировки
- PNG — для предпросмотра (обратно совместимый)

Формат BMP определяется по export_mode из конфига станка (v3):
  - laser_standard: export_mode='8bit' → 8-bit grayscale
  - laser_80w: export_mode='8bit' → 8-bit grayscale (Engrave сам растрирует)
  - impact: export_mode='8bit' → 8-bit grayscale (256 уровней силы удара)
  - Любая машина: export_mode='1bit' → 1-bit BMP с дизерингом (dither_method_1bit)

DEPRECATED: dither_method → используйте export_mode + dither_method_1bit
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


def _uint8_to_mode1(arr: np.ndarray, size: tuple[int, int]) -> Image.Image:
    """BE-L13: Создать 1-bit изображение напрямую из uint8 массива (0/255).

    Без двойной конвертации fromarray(L).convert('1'):
    упаковываем булеву маску в packed bitmap для Pillow mode '1'.
    """
    # bool array: 255 → True (белый), 0 → False (чёрный)
    bool_arr = arr >= 128
    # PIL mode '1' ожидает packed bits: каждый байт = 8 пикселей, MSB first
    packed = np.packbits(bool_arr, axis=1)
    return Image.frombytes('1', size, packed.tobytes())


def _error_diffusion_dither(img_gray, weights) -> Image.Image:
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
        # BE-L13: Собираем 1-bit напрямую из uint8 (0/255) без двойной конвертации
        return _uint8_to_mode1(result, img_gray.size)

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

    # BE-L13: Собираем 1-bit напрямую из uint8 (0/255) без двойной конвертации
    return _uint8_to_mode1(result, img_gray.size)


def stucki_dither(img_gray) -> Image.Image:
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


def jarvis_dither(img_gray) -> Image.Image:
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


def _apply_dither(img_gray, method='jarvis') -> Image.Image:
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


def save_bmp_8bit(img, output_path, machine_type=None, step_mm=None) -> None:
    """Сохранить изображение как 8-bit grayscale BMP с палитрой R=G=B.

    Формат: BMP, 8-bit indexed, палитра 256 записей (0,0,0)...(255,255,255).
    Это стандартный формат для ударной гравировки и лазерной в полутоновом режиме.

    DPI в заголовке вычисляется из step_mm: dpi = 25.4 / step_mm.
    Engrave НЕ использует DPI из заголовка, но показывает предупреждение
    при несоответствии — поэтому пишем корректное значение.

    Args:
        img: PIL.Image (RGB или L)
        output_path: путь к выходному BMP-файлу
        machine_type: тип станка (для логирования)
        step_mm: шаг ЧПУ в мм — для записи DPI в заголовок BMP (None = не писать DPI)
    """
    # Конвертируем в grayscale если нужно
    if img.mode == 'RGB':
        img_gray = img.convert('L')
    elif img.mode == 'RGBA':
        img_gray = img.convert('L')
    elif img.mode == '1':
        img_gray = img.convert('L')
    elif img.mode == 'P':
        img_gray = img.convert('L')
    else:
        img_gray = img

    # DPI из step_mm (чтобы Engrave не ругался)
    save_kwargs = {'format': 'BMP'}
    if step_mm and step_mm > 0:
        dpi = round(25.4 / step_mm, 1)
        save_kwargs['dpi'] = (dpi, dpi)

    # Создаём 8-bit BMP с палитрой R=G=B
    # PIL автоматически создаёт правильную grayscale палитру при сохранении L как BMP
    img_gray.save(output_path, **save_kwargs)

    path = Path(output_path)
    size_kb = path.stat().st_size / 1024
    dpi_str = f", DPI={save_kwargs['dpi'][0]:.1f}" if 'dpi' in save_kwargs else ""
    logger.info(
        "BMP 8-bit saved: %s (%dx%d, %.0f KB, machine=%s%s)",
        output_path, img_gray.width, img_gray.height, size_kb, machine_type, dpi_str,
    )


def save_bmp_1bit(img, output_path, machine_type=None, dither_method=None) -> None:
    """Сохранить изображение как 1-bit монохромный BMP с дизерингом.

    Формат: BMP, 1-bit (два цвета: чёрный и белый).
    Полутона имитируются дизерингом. Стандарт для лазерной гравировки 80W+.

    Белый = лазер включён, чёрный = лазер выключен.

    Args:
        img: PIL.Image (RGB или L)
        output_path: путь к выходному BMP-файлу
        machine_type: тип станка (для логирования)
        dither_method: 'jarvis' | 'stucki' | None (авто)
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

    img_dithered = _apply_dither(img_gray, method)

    # Сохраняем как 1-bit BMP
    img_dithered.save(output_path, format='BMP')

    path = Path(output_path)
    size_kb = path.stat().st_size / 1024
    logger.info(
        "BMP 1-bit (%s dither) saved: %s (%dx%d, %.0f KB, machine=%s)",
        method, output_path, img_dithered.width, img_dithered.height,
        size_kb, machine_type,
    )


def export_result(img, output_path, machine_type="laser_standard", fmt="bmp",
                  dither_method=None, export_mode=None, step_mm=None,
                  dither_method_1bit=None,
                  save_png_preview=False) -> str:
    """Экспорт результата пайплайна в нужном формате.

    Логика выбора формата (приоритет от высшего к низшему):
    1. Явный fmt='bmp_8bit' или fmt='bmp_1bit' — перекрывает export_mode
    2. export_mode='8bit' → 8-bit grayscale BMP (БЕЗ дизеринга)
    3. export_mode='1bit' → 1-bit BMP с дизерингом (dither_method_1bit)
    4. export_mode=None → fallback на dither_method (обратная совместимость)

    Машины по умолчанию (v3):
    - laser_standard: export_mode='8bit' → 8-bit grayscale
    - laser_80w: export_mode='8bit' → 8-bit grayscale (Engrave сам растрирует)
    - impact: export_mode='8bit' → 8-bit grayscale (256 уровней силы удара)

    Args:
        img: PIL.Image (RGB или L) — финальное изображение от пайплайна
        output_path: путь к выходному файлу (расширение будет заменено на .bmp)
        machine_type: тип станка ('laser_standard', 'laser_80w', 'impact')
        fmt: формат экспорта ('bmp', 'bmp_1bit', 'bmp_8bit', 'png')
        dither_method: DEPRECATED — алгоритм дизеринга, используйте export_mode
        export_mode: режим экспорта ('8bit' | '1bit') — определяет формат BMP
        step_mm: шаг ЧПУ в мм — для записи DPI в заголовок BMP
        dither_method_1bit: алгоритм дизеринга для 1-bit режима ('jarvis' | 'stucki')
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
        # Явный запрос 8-bit grayscale — перекрывает export_mode
        save_bmp_8bit(img, bmp_path, machine_type=machine_type, step_mm=step_mm)
    elif fmt == "bmp_1bit":
        # Явный запрос 1-bit — дизеринг обязателен
        method = dither_method_1bit or dither_method or "jarvis"
        save_bmp_1bit(img, bmp_path, machine_type=machine_type,
                      dither_method=method)
    elif export_mode == "1bit":
        # Конфиг станка: 1-bit режим → дизеринг
        method = dither_method_1bit or dither_method or "jarvis"
        save_bmp_1bit(img, bmp_path, machine_type=machine_type,
                      dither_method=method)
    elif export_mode == "8bit":
        # Конфиг станка: 8-bit режим → grayscale BMP
        save_bmp_8bit(img, bmp_path, machine_type=machine_type, step_mm=step_mm)
    elif fmt == "bmp" and dither_method and dither_method != "none":
        # Fallback: старый путь через dither_method (обратная совместимость)
        save_bmp_1bit(img, bmp_path, machine_type=machine_type,
                      dither_method=dither_method)
    else:
        # Default: 8-bit grayscale
        save_bmp_8bit(img, bmp_path, machine_type=machine_type, step_mm=step_mm)

    # PNG preview — только по явному запросу (save_png_preview=True)
    if save_png_preview:
        png_path = str(output.with_suffix(".png"))
        if img.mode != 'RGB':
            img.convert('RGB').save(png_path, format='PNG')
        else:
            img.save(png_path, format='PNG')
        logger.info("PNG preview saved: %s", png_path)

    return bmp_path
