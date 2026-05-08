"""Детекция зоны лица и генерация масок лица/волос.

Трёхуровневая стратегия (C.1):
  1. Улучшенная эвристика (профиль ширины маски) — покрывает 85-90%
  2. Ручной овал (FaceOvalOverlay) — покрывает оставшиеся 10-15%
  3. mediapipe FaceLandmarker — в будущем, когда фичи #2, #3, #6 будут готовы
"""

import logging

import numpy as np
from PIL import Image, ImageDraw, ImageChops

logger = logging.getLogger(__name__)


def _detect_face_by_width_profile(subject_mask, img_height, img_width):
    """Найти зону лица по профилю ширины маски.

    Первый локальный максимум ширины сверху = уровень скул.
    Лицо ≈ от макушки до скул с запасом вниз.

    Args:
        subject_mask: PIL.Image в режиме L (маска субъекта)
        img_height: высота изображения
        img_width: ширина изображения

    Returns:
        dict | None: {cx, cy, rx, ry, source} или None (если профиль нечитаем)
    """
    mask_arr = np.array(subject_mask) > 128
    widths = mask_arr.sum(axis=1)  # ширина по каждой строке

    # Скользящее среднее (сгладить шум маски)
    kernel_size = max(1, img_height // 50)  # адаптивный kernel
    kernel = np.ones(kernel_size) / kernel_size
    smooth = np.convolve(widths, kernel, mode='same')

    # Первый локальный максимум сверху = скулы
    face_row = None
    for i in range(kernel_size, len(smooth) - kernel_size):
        if smooth[i] > smooth[i - 1] and smooth[i] >= smooth[i + 1]:
            face_row = i  # строка максимальной ширины
            break

    if face_row is None:
        return None  # профиль нечитаем → fallback

    # Лицо ≈ от макушки до скул с запасом вниз
    # Высота лица ≈ ширина в точке скул (лицо ~овальное)
    face_width_px = smooth[face_row]
    face_height_px = int(face_width_px * 1.2)  # с запасом

    # Центр овала
    cx_norm = 0.5  # по горизонтали — центр
    cy_norm = (face_row - face_height_px // 2) / img_height
    rx_norm = (face_width_px / 2) / img_width
    ry_norm = (face_height_px / 2) / img_height

    # Sanity check: координаты в пределах (0, 1)
    cx_norm = max(0.1, min(0.9, cx_norm))
    cy_norm = max(0.05, min(0.7, cy_norm))
    rx_norm = max(0.05, min(0.45, rx_norm))
    ry_norm = max(0.05, min(0.45, ry_norm))

    logger.info(
        "Face detection (width profile): face_row=%d, cx=%.2f, cy=%.2f, "
        "rx=%.2f, ry=%.2f",
        face_row, cx_norm, cy_norm, rx_norm, ry_norm,
    )

    return {
        "cx": cx_norm, "cy": cy_norm,
        "rx": rx_norm, "ry": ry_norm,
        "source": "heuristic",
    }


def detect_face_oval(img_gray, subject_mask=None) -> dict:
    """Детекция зоны лица → FaceOvalParams.

    Трёхуровневая стратегия:
      1. Улучшенная эвристика (профиль ширины маски) — покрывает 85-90%
      2. Ручной овал (FaceOvalOverlay) — покрывает оставшиеся 10-15%
      3. mediapipe FaceLandmarker — в будущем

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        subject_mask: PIL.Image в режиме L (маска субъекта) или None

    Returns:
        dict: {cx, cy, rx, ry, source}
    """
    if subject_mask is not None:
        result = _detect_face_by_width_profile(
            subject_mask, img_gray.height, img_gray.width)
        if result is not None:
            return result

    # Fallback: текущая эвристика (верхние 45%)
    logger.info("Face detection: width profile failed, using legacy fallback")
    return {
        "cx": 0.5, "cy": 0.25,
        "rx": 0.25, "ry": 0.20,
        "source": "heuristic_legacy",
    }


def generate_face_mask(width, height, face_oval, subject_mask):
    """Создать маску лица из овала + маски субъекта.

    Args:
        width: ширина изображения
        height: высота изображения
        face_oval: dict {cx, cy, rx, ry} или None
        subject_mask: PIL.Image в режиме L (маска субъекта)

    Returns:
        PIL.Image: маска лица (L), или None если face_oval=None и нет маски
    """
    if face_oval is None:
        return _heuristic_face_mask(width, height, subject_mask, top_ratio=0.45)

    cx = int(face_oval['cx'] * width)
    cy = int(face_oval['cy'] * height)
    rx = int(face_oval['rx'] * width)
    ry = int(face_oval['ry'] * height)

    # Защита от нулевых/отрицательных размеров
    rx = max(1, rx)
    ry = max(1, ry)

    oval = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(oval)
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)

    if subject_mask is not None:
        oval = ImageChops.multiply(oval, subject_mask)

    return oval


def generate_hair_mask(face_mask, subject_mask, gap_ratio=0.05):
    """Маска волос = субъект выше овала лица с зазором.

    gap_ratio — доля высоты изображения (масштабонезависимо).

    Args:
        face_mask: PIL.Image в режиме L (маска лица)
        subject_mask: PIL.Image в режиме L (маска субъекта)
        gap_ratio: зазор между верхом лица и началом зоны волос,
            как доля высоты изображения (по умолчанию 0.05 = 5%)

    Returns:
        PIL.Image: маска волос (L)
    """
    if face_mask is None or subject_mask is None:
        return Image.new('L', (subject_mask.width if subject_mask else 512,
                                subject_mask.height if subject_mask else 512), 0)

    width, height = face_mask.size
    gap_px = int(height * gap_ratio)

    # Находим верхнюю границу маски лица
    face_arr = np.array(face_mask) > 128
    subject_arr = np.array(subject_mask) > 128

    # Маска волос: субъект выше (верх овала - gap)
    # Сначала находим bounding box маски лица
    face_rows = np.any(face_arr, axis=1)
    face_top = np.argmax(face_rows) if face_rows.any() else 0

    hair_zone_top = max(0, face_top - gap_px)

    hair_arr = np.zeros_like(subject_arr)
    hair_arr[:hair_zone_top, :] = subject_arr[:hair_zone_top, :]

    return Image.fromarray((hair_arr.astype(np.uint8) * 255), "L")


def _heuristic_face_mask(width, height, subject_mask, top_ratio=0.45):
    """Legacy: маска лица = верхние top_ratio% маски субъекта."""
    if subject_mask is None:
        return None

    mask_arr = np.array(subject_mask)
    cutoff = int(height * top_ratio)
    face_arr = np.zeros_like(mask_arr)
    face_arr[:cutoff, :] = mask_arr[:cutoff, :]

    return Image.fromarray(face_arr, "L")
