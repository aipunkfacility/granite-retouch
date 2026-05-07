"""Модуль преданализа входного grayscale-изображения."""

import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def analyze_input(gray_image: Image.Image, subject_mask: np.ndarray) -> dict:
    """Измеряет тональные характеристики входного grayscale-файла.

    Вызывается ОДИН раз после шага 2 (Grayscale), когда доступны
    grayscale-изображение и subject_mask.
    Результат передаётся во все последующие шаги.

    Args:
        gray_image: PIL.Image в режиме L (grayscale)
        subject_mask: numpy array — маска субъекта (bool или 0/255)

    Returns:
        dict с метриками для адаптивных доработок пайплайна.
    """
    img_arr = np.array(gray_image, dtype=np.float32)

    # Нормализуем маску в bool
    if subject_mask.dtype != bool:
        mask_bool = np.array(subject_mask) > 128
    else:
        mask_bool = subject_mask

    face_pixels = img_arr[mask_bool]
    bg_pixels = img_arr[~mask_bool]

    if len(face_pixels) == 0:
        logger.warning("analyze_input: нет пикселей субъекта в маске")
        return _empty_result()

    result = {
        # Основные метрики (лицо)
        'median_brightness': float(np.median(face_pixels)),
        'mean_brightness': float(np.mean(face_pixels)),

        # Тональный диапазон (лицо)
        'p10_brightness': float(np.percentile(face_pixels, 10)),
        'p25_brightness': float(np.percentile(face_pixels, 25)),
        'p75_brightness': float(np.percentile(face_pixels, 75)),
        'p90_brightness': float(np.percentile(face_pixels, 90)),
        'tonal_range': float(np.percentile(face_pixels, 90) - np.percentile(face_pixels, 10)),

        # Проблемные зоны (лицо)
        'highlight_clipping_pct': float(np.sum(face_pixels >= 250) / len(face_pixels) * 100),
        'shadow_clipping_pct': float(np.sum(face_pixels <= 5) / len(face_pixels) * 100),

        # Метрики фона (для P3: адаптивный glow)
        'bg_median_brightness': float(np.median(bg_pixels)) if len(bg_pixels) > 0 else 0,
        'bg_mean_brightness': float(np.mean(bg_pixels)) if len(bg_pixels) > 0 else 0,
        'subject_separation': float(abs(np.median(face_pixels) - (np.median(bg_pixels) if len(bg_pixels) > 0 else 0))),

        # Классификация входа
        'input_class': _classify_input(face_pixels),
    }

    logger.info(
        "Input analysis: median=%.1f, class=%s, range=%.1f, p90=%.1f, clipping=%.1f%%",
        result['median_brightness'], result['input_class'],
        result['tonal_range'], result['p90_brightness'],
        result['highlight_clipping_pct'],
    )

    return result


def _classify_input(face_pixels: np.ndarray) -> str:
    """Классификация входного файла по яркости."""
    median = float(np.median(face_pixels))
    if median < 120:
        return 'dark'
    elif median < 180:
        return 'medium'
    elif median < 220:
        return 'bright'
    else:
        return 'overbright'


def _empty_result() -> dict:
    """Пустой результат при отсутствии субъекта."""
    return {
        'median_brightness': 0, 'mean_brightness': 0,
        'p10_brightness': 0, 'p25_brightness': 0,
        'p75_brightness': 0, 'p90_brightness': 0,
        'tonal_range': 0,
        'highlight_clipping_pct': 0, 'shadow_clipping_pct': 0,
        'bg_median_brightness': 0, 'bg_mean_brightness': 0,
        'subject_separation': 0,
        'input_class': 'dark',
    }
