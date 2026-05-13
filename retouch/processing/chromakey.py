"""Удаление синего хромакея + fringe removal + градиентная альфа-маска.

PERF: uint8 вместо float32 для основного массива — -48 MB на 2048×2048
FIX: Градиентная маска вместо бинарного порога + contour tracing —
     плавный контур без зазубрин на диагоналях. Переход следует за
     градиентом синевы, а не за пиксельной решёткой.
"""

import logging

from PIL import Image, ImageFilter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from scipy.ndimage import gaussian_filter
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

logger = logging.getLogger(__name__)


def _compute_blue_strength(r, g, b, threshold):
    """Градиент 'синевы': 0=субъект, 1=чистый синий фон.

    Субъект всегда grayscale (B≈R≈G), только фон #0000FF.
    Поэтому gradient можно делать агрессивнее без риска съесть субъект.

    Использует soft-step вместо бинарного порога:
    - excess < threshold - half_band → 0 (твёрдый субъект)
    - excess > threshold + half_band → 1 (твёрдый фон)
    - в промежутке → линейный градиент

    half_band = max(threshold * 0.5, 8) — агрессивный, но безопасный:
    grayscale-субъект (excess≈0) далеко от transition zone.

    Args:
        r, g, b: ndarray uint8 — каналы изображения
        threshold: int — порог синевы (из конфига)

    Returns:
        ndarray float32 — 0.0 (субъект) … 1.0 (фон)
    """
    b_f = b.astype(np.float32)
    max_rg = np.maximum(r.astype(np.float32), g.astype(np.float32))
    blue_excess = b_f - max_rg
    half_band = max(threshold * 0.5, 8.0)
    blue_strength = np.clip(
        (blue_excess - threshold + half_band) / (2 * half_band), 0, 1
    )
    return blue_strength


def remove_blue_background(img, threshold=30, fringe_radius=3,
                           mask_soft_sigma=1.5, contour_smooth_epsilon=0.002):
    """Удалить синий хромакей и убрать синие рефлексы (fringe) по краям.

    Использует градиентную маску (soft-step) вместо бинарного порога.
    Переход следует за градиентом синевы — плавный контур без зазубрин.

    Fallback на Pillow при отсутствии numpy.

    Args:
        img: PIL.Image в режиме RGBA
        threshold: порог для определения синего хромакея
        fringe_radius: радиус расширения маски для fringe removal (px)
        mask_soft_sigma: sigma Gaussian blur для софт-краёв маски.
            0 = маска без дополнительного размытия (градиент всё равно мягкий).
            1.0-2.0 = более широкая переходная зона (рекомендуется).
        contour_smooth_epsilon: DEPRECATED — игнорируется.
            Градиентная маска не использует contour tracing.
            Параметр оставлен для совместимости сигнатуры.

    Returns:
        tuple: (img_without_bg, subject_mask) — оба PIL.Image
    """
    if HAS_NUMPY:
        return _remove_blue_numpy(img, threshold, fringe_radius,
                                  mask_soft_sigma, contour_smooth_epsilon)
    return _remove_blue_pillow(img, threshold, fringe_radius)


def _make_smooth_mask(binary_mask, smooth_epsilon=0.002):
    """DEPRECATED — не используется в основном пайплайне.

    Заменено на градиентную маску (_compute_blue_strength).
    Функция оставлена для внешних вызовов и обратной совместимости.

    Создать антиалиасную маску из бинарной через OpenCV contour tracing.

    Алгоритм:
    1. findContours — извлечь векторный контур из бинарной маски
    2. drawContours(LINE_AA) — растеризовать с субпиксельным антиалиасингом

    Args:
        binary_mask: ndarray bool — бинарная маска субъекта (True = субъект)
        smooth_epsilon: float — DEPRECATED, игнорируется.

    Returns:
        ndarray uint8 — маска 0-255 с антиалиасными краями
    """
    if not HAS_CV2:
        # Fallback: бинарная маска без антиалиасинга
        logger.warning(
            "opencv-python not available, falling back to binary mask — "
            "contour may have staircase artifacts on diagonals. "
            "Install: uv sync"
        )
        return binary_mask.astype(np.uint8) * 255

    mask_uint8 = binary_mask.astype(np.uint8) * 255

    # 1. Трассировка контура
    contours, _ = cv2.findContours(
        mask_uint8,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return mask_uint8

    # 2. Выбрать самый большой контур (по площади)
    main_contour = max(contours, key=cv2.contourArea)

    logger.info(
        "OpenCV: anti-aliased mask (contour points=%d, approxPolyDP=OFF)",
        len(main_contour),
    )

    # 3. Растеризовать с антиалиасингом
    result = np.zeros_like(mask_uint8)
    cv2.drawContours(
        result,
        [main_contour],
        contourIdx=-1,
        color=255,
        thickness=cv2.FILLED,
        lineType=cv2.LINE_AA,
    )

    return result


def _smooth_dilate(mask, radius):
    """Изотропная дилатация через GaussianBlur — без лесенки на диагоналях.

    binary_dilation с дефолтным structuring element (крест) даёт
    ступеньки на диагональных краях. GaussianBlur + threshold
    эквивалентен дилатации с круглым ядром.
    """
    if not HAS_SCIPY:
        mask_img = Image.fromarray(mask.astype(np.uint8) * 255)
        blurred = mask_img.filter(ImageFilter.GaussianBlur(radius=radius))
        return np.array(blurred) > 128
    blurred = gaussian_filter(mask.astype(np.float32), sigma=radius)
    return blurred > 0.5


def _smooth_erode(mask, radius):
    """Изотропная эрозия через GaussianBlur — без лесенки на диагоналях.

    binary_erosion с дефолтным structuring element (крест) даёт
    ступеньки. Эрозия = инвертировать → размыть → порог → инвертировать.
    """
    if not HAS_SCIPY:
        mask_img = Image.fromarray((~mask).astype(np.uint8) * 255)
        blurred = mask_img.filter(ImageFilter.GaussianBlur(radius=radius))
        return np.array(blurred) < 128
    inv = (~mask).astype(np.float32)
    blurred = gaussian_filter(inv, sigma=radius)
    return blurred < 0.5


def _remove_blue_numpy(img, threshold=30, fringe_radius=3,
                       mask_soft_sigma=1.5, contour_smooth_epsilon=0.002):
    """numpy-реализация: удаление хромакея + fringe + градиентная маска.

    Оптимизация памяти: uint8 вместо float32 для основного массива.
    float32 используется только в fringe-зоне и для градиентной маски.

    Градиентная маска: вместо бинарного порога B > R + threshold
    вычисляется «степень синевы» через soft-step. Альфа-канал = 1 - blue_strength.
    Переход следует за реальным градиентом синевы на границе — плавный
    контур без зазубрин, работает без cv2.

    Fringe removal использует бинарный порог (отдельно от градиентной альфы)
    для коррекции RGB-каналов пограничных пикселей.
    """

    # uint8 — основная работа (4 байт/пиксель вместо 16 при float32)
    arr = np.array(img)  # uint8 RGBA
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    # --- Бинарный blue_mask для fringe (старая логика) ---
    # Fringe нужен для коррекции RGB-каналов, отдельно от градиентной альфы
    blue_mask = (b.astype(np.int16) > r.astype(np.int16) + threshold) & \
                (b.astype(np.int16) > g.astype(np.int16) + threshold)

    # --- Fringe removal (float только в зоне ореола) ---
    if fringe_radius > 0:
        expanded_mask = _smooth_dilate(blue_mask, radius=fringe_radius)
    else:
        expanded_mask = blue_mask

    fringe_zone = expanded_mask & ~blue_mask
    if np.any(fringe_zone):
        fringe_ys, fringe_xs = np.where(fringe_zone)
        b_f = b[fringe_ys, fringe_xs].astype(np.float32)
        r_f = r[fringe_ys, fringe_xs].astype(np.float32)
        g_f = g[fringe_ys, fringe_xs].astype(np.float32)
        fringe_blue_strength = np.clip(
            (b_f - np.maximum(r_f, g_f)) / (threshold * 2), 0, 1
        )
        fringe_factor = fringe_blue_strength
        b_corrected = np.clip(
            b_f * (1 - fringe_factor) + np.maximum(r_f, g_f) * fringe_factor,
            0, 255
        ).astype(np.uint8)
        arr[fringe_ys, fringe_xs, 2] = b_corrected

    # --- Градиентная маска для альфа-канала ---
    blue_strength = _compute_blue_strength(r, g, b, threshold)
    subject_alpha = 1.0 - blue_strength

    # Фон = чёрный прозрачный (RGB обнулён для чистоты)
    arr[blue_mask] = [0, 0, 0, 0]

    # Альфа-канал = градиентная маска
    arr[..., 3] = (subject_alpha * 255).astype(np.uint8)

    # --- Subject mask ---
    if mask_soft_sigma > 0:
        subject_mask_float = subject_alpha * 255.0
        if HAS_SCIPY:
            subject_mask_float = gaussian_filter(
                subject_mask_float, sigma=mask_soft_sigma
            )
        else:
            # Pillow fallback для gaussian_filter
            sm_img = Image.fromarray(subject_mask_float.astype(np.uint8))
            subject_mask_float = np.array(
                sm_img.filter(ImageFilter.GaussianBlur(radius=mask_soft_sigma)),
                dtype=np.float32
            )
        # Внутренность субъекта = 255 (не размываем вглубь)
        inner_solid = _smooth_erode(
            blue_strength < 0.01, radius=max(1, int(mask_soft_sigma * 2))
        )
        subject_mask_float[inner_solid] = 255.0
        subject_arr = np.clip(subject_mask_float, 0, 255).astype(np.uint8)
    else:
        subject_arr = (subject_alpha * 255).astype(np.uint8)

    return Image.fromarray(arr), Image.fromarray(subject_arr)


def _remove_blue_pillow(img, threshold=30, fringe_radius=3):
    """Pillow-fallback: удаление хромакея + упрощённый fringe removal.

    Примечание: Pillow-fallback не поддерживает mask_soft_sigma —
    всегда возвращает бинарную маску. numpy-реализация доступна.
    Требуется scipy для fringe removal; если scipy недоступна —
    fringe_radius игнорируется.
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
