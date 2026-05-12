"""Удаление синего хромакея + fringe removal + софт-маска.

PERF: uint8 вместо float32 для основного массива — -48 MB на 2048×2048
FIX: Антиалиасная маска через OpenCV contour tracing — гладкий контур без лесенки
"""

import logging

from PIL import Image

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

logger = logging.getLogger(__name__)


def remove_blue_background(img, threshold=30, fringe_radius=3,
                           mask_soft_sigma=1.5, contour_smooth_epsilon=0.002):
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
        contour_smooth_epsilon: DEPRECATED — параметр approxPolyDP, теперь
            игнорируется. approxPolyDP убран: он создавал полигон с малым
            числом вершин и прямыми отрезками, что давало чёрную угловатую
            полосу между субъектом и outer glow. Параметр оставлен для
            совместимости сигнатуры.

    Returns:
        tuple: (img_without_bg, subject_mask) — оба PIL.Image
    """
    if HAS_NUMPY:
        return _remove_blue_numpy(img, threshold, fringe_radius,
                                  mask_soft_sigma, contour_smooth_epsilon)
    return _remove_blue_pillow(img, threshold, fringe_radius)


def _make_smooth_mask(binary_mask, smooth_epsilon=0.002):
    """Создать антиалиасную маску из бинарной через OpenCV contour tracing.

    Алгоритм:
    1. findContours — извлечь векторный контур из бинарной маски
    2. drawContours(LINE_AA) — растеризовать с субпиксельным антиалиасингом

    FIX: approxPolyDP убран — он создавал полигон с малым числом вершин
    и прямыми отрезками. На вогнутых участках контура (шея-плечи, уши)
    прямые линии между вершинами уходили за пределы реального контура
    человека. Это создавало чёрную угловатую полосу между субъектом
    и outer glow: в этих зонах subject_mask=255 (внутри полигона),
    но img_gray — тёмный фон, а glow_mask=0 (внутри «субъекта»).

    Антиалиасинг LINE_AA на исходном контуре даёт гладкие края
    без потери точности формы.

    Args:
        binary_mask: ndarray bool — бинарная маска субъекта (True = субъект)
        smooth_epsilon: float — DEPRECATED, игнорируется.
            Оставлен для совместимости сигнатуры.

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
    # CHAIN_APPROX_SIMPLE — убирает избыточные точки на прямых отрезках,
    # сохраняя точность кривых. Без approxPolyDP — контур следует
    # пиксельной границе маски максимально точно.
    contours, _ = cv2.findContours(
        mask_uint8,
        cv2.RETR_EXTERNAL,       # Только внешние контуры (без дыр)
        cv2.CHAIN_APPROX_SIMPLE  # Упрощение: только горизонтальные/вертикальные
    )

    if not contours:
        return mask_uint8

    # 2. Выбрать самый большой контур (по площади)
    main_contour = max(contours, key=cv2.contourArea)

    # Логируем число вершин для диагностики
    logger.info(
        "OpenCV: anti-aliased mask (contour points=%d, approxPolyDP=OFF)",
        len(main_contour),
    )

    # 3. Растеризовать с антиалиасингом
    # LINE_AA даёт плавный субпиксельный градиент на контуре.
    # Без approxPolyDP — контур точно повторяет исходную маску.
    result = np.zeros_like(mask_uint8)
    cv2.drawContours(
        result,
        [main_contour],
        contourIdx=-1,           # Все контуры в списке (у нас один)
        color=255,
        thickness=cv2.FILLED,    # Заливка
        lineType=cv2.LINE_AA,    # 8-связная линия с субпиксельным АА
    )

    return result


def _smooth_dilate(mask, radius):
    """Изотропная дилатация через GaussianBlur — без лесенки на диагоналях.

    binary_dilation с дефолтным structuring element (крест) даёт
    ступеньки на диагональных краях. GaussianBlur + threshold
    эквивалентен дилатации с круглым ядром.
    """
    from scipy.ndimage import gaussian_filter
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


def _remove_blue_numpy(img, threshold=30, fringe_radius=3,
                       mask_soft_sigma=1.5, contour_smooth_epsilon=0.002):
    """numpy-реализация: удаление хромакея + fringe + антиалиасная маска.

    Оптимизация памяти: uint8 вместо float32 для основного массива.
    float32 используется только в fringe-зоне (гораздо меньше всего изображения).

    Если доступен OpenCV (cv2): контур маски трассируется в векторный путь,
    сглаживается approxPolyDP и растеризуется с LINE_AA антиалиасингом.
    Это даёт плавный контур без лесенки на диагоналях.

    Если cv2 недоступен: fallback на GaussianBlur-подход (хуже, но работает).
    """
    from scipy.ndimage import gaussian_filter

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
        fringe_ys, fringe_xs = np.where(fringe_zone)
        b_f = b[fringe_ys, fringe_xs].astype(np.float32)
        r_f = r[fringe_ys, fringe_xs].astype(np.float32)
        g_f = g[fringe_ys, fringe_xs].astype(np.float32)
        blue_strength = np.clip((b_f - np.maximum(r_f, g_f)) / (threshold * 2), 0, 1)
        fringe_factor = blue_strength
        b_corrected = (b_f * (1 - fringe_factor) + np.maximum(r_f, g_f) * fringe_factor).astype(np.uint8)
        arr[fringe_ys, fringe_xs, 2] = b_corrected

    subject_bool = ~blue_mask

    if HAS_CV2:
        # --- OpenCV: антиалиасная маска через векторный контур ---
        # Трассировка → сглаживание → растеризация с LINE_AA
        aa_mask = _make_smooth_mask(subject_bool, smooth_epsilon=contour_smooth_epsilon)

        # Фон = чёрный прозрачный
        arr[blue_mask] = [0, 0, 0, 0]

        # Альфа-канал = антиалиасная маска
        # На контуре: aa_mask содержит 1-254 (плавный градиент от LINE_AA)
        # Внутри: 255, снаружи: 0
        arr[..., 3] = aa_mask

        # subject_mask: если mask_soft_sigma > 0 — дополнительное размытие
        # для плавного перехода в glow/face_correction
        if mask_soft_sigma > 0:
            subject_mask_float = aa_mask.astype(np.float32)
            subject_mask_float = gaussian_filter(subject_mask_float, sigma=mask_soft_sigma)
            # Возвращаем 255 внутри (не размываем вглубь субъекта)
            inner = aa_mask > 200
            inner_solid = _smooth_erode(inner, radius=max(1, int(mask_soft_sigma * 2)))
            subject_mask_float[inner_solid] = 255.0
            subject_arr = np.clip(subject_mask_float, 0, 255).astype(np.uint8)
        else:
            subject_arr = aa_mask

    else:
        # --- Fallback: GaussianBlur-подход (без cv2) ---
        bg_soft = gaussian_filter(blue_mask.astype(np.float32), sigma=1.0)

        arr[blue_mask] = [0, 0, 0, 0]
        alpha_aa = np.clip((1.0 - bg_soft) * 255.0, 0, 255)
        alpha_aa[blue_mask] = 0.0
        inner_solid = _smooth_erode(subject_bool, radius=2)
        alpha_aa[inner_solid] = 255.0
        arr[..., 3] = alpha_aa.astype(np.uint8)

        if mask_soft_sigma > 0:
            subject_mask_float = subject_bool.astype(np.float32) * 255.0
            subject_mask_float = gaussian_filter(subject_mask_float, sigma=mask_soft_sigma)
            inner_solid = _smooth_erode(subject_bool, radius=max(1, int(mask_soft_sigma * 2)))
            subject_mask_float[inner_solid] = 255.0
            subject_arr = np.clip(subject_mask_float, 0, 255).astype(np.uint8)
        else:
            subject_arr = subject_bool.astype(np.uint8) * 255

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
