"""Unified soft rolloff — замена разрозненным ceiling/clamp реализациям.

Все шаги используют soft_rolloff_masked() вместо локального np.minimum()
и np.clip(). Compression — параметр конфига/PipelinePlan, не хардкод.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def soft_rolloff_masked(
    arr: np.ndarray,
    mask: np.ndarray,
    knee: float,
    ceiling: float,
    compression: float = 0.35,
) -> np.ndarray:
    """Мягкое сжатие светов выше knee с ограничением на ceiling.

    Заменяет разрозненные реализации в levels.py, unsharp.py, pipeline.py.

    Args:
        arr: float array (H, W) — изображение
        mask: bool или uint8 array (H, W) — маска применения
        knee: порог начала сжатия (обычно ceiling * 0.90)
        ceiling: абсолютный потолок
        compression: доля excess, сохраняемая выше knee (0.35 = 35%)

    Returns:
        np.ndarray: arr с применённым rolloff (копия при необходимости).
    """
    if arr.dtype != np.float32 and arr.dtype != np.float64:
        arr = arr.astype(np.float32)

    mask_bool = mask > 128 if mask.dtype != bool else mask

    if not mask_bool.any():
        return arr

    # Работаем на копии masked области
    masked = arr[mask_bool].copy()
    over = masked > knee

    if over.any():
        excess = masked[over] - knee
        masked[over] = knee + excess * compression

    arr[mask_bool] = np.clip(masked, 0, ceiling)
    return arr
