"""Unified soft rolloff — замена разрозненным ceiling/clamp реализациям.

Все шаги используют soft_rolloff_masked() вместо локального np.minimum()
и np.clip(). Compression — параметр конфига/PipelinePlan, не хардкод.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from retouch.processing.analysis.zones import ZoneMasks

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


def build_face_safe_rolloff_mask(
    subject_mask: np.ndarray,
    face_mask: np.ndarray | None = None,
    zone_masks: ZoneMasks | None = None,
    *,
    primary_zone: str = "exclude_face_skin",
    logger_prefix: str = "rolloff",
) -> np.ndarray | None:
    """Построить rolloff-маску, защищающую лицо от пережига.

    Выбор primary-зоны (параметр primary_zone):
    - "exclude_face_skin": rolloff на субъект МИНУС face_skin.
      Используется postprocess.py после gamma.
    - "highlights_only": rolloff только на highlights зону.
      Используется highlight_rolloff в steps.py.

    Fallback-цепочка (когда primary-зона недоступна):
    1. face_mask → субъект минус лицо (менее точная маска, warning)
    2. None → пропустить rolloff (предотвращает пережиг, warning)

    Returns:
        np.ndarray: rolloff-маска (uint8), или None если rolloff пропускается.
    """
    subj_bool = np.array(subject_mask) > 128

    # --- Primary zone ---
    if primary_zone == "exclude_face_skin":
        if zone_masks is not None and zone_masks.face_skin is not None:
            fs = zone_masks.face_skin
            fs_bool = fs > 128 if fs.dtype != bool else fs
            rolloff_bool = subj_bool & ~fs_bool
            logger.info(
                "%s: rolloff on subject minus face_skin (%d px)",
                logger_prefix, int(rolloff_bool.sum()),
            )
            return rolloff_bool.astype(np.uint8) * 255

    elif primary_zone == "highlights_only":
        if (
            zone_masks is not None
            and zone_masks.highlights is not None
            and zone_masks.highlights.any()
        ):
            return (zone_masks.highlights > 0).astype(np.uint8) * 255

    # --- Fallback: face_mask → субъект минус лицо ---
    if face_mask is not None and np.any(np.array(face_mask) > 128):
        face_bool = np.array(face_mask) > 128
        rolloff_bool = subj_bool & ~face_bool
        logger.warning(
            "%s: primary zone unavailable, using face_mask fallback "
            "to exclude face (%d px). Less precise than zone_masks — "
            "consider ensuring zone_masks are built correctly.",
            logger_prefix, int(rolloff_bool.sum()),
        )
        return rolloff_bool.astype(np.uint8) * 255

    # --- Нет защиты — пропускаем rolloff ---
    logger.warning(
        "%s: both primary zone and face_mask unavailable — "
        "skipping rolloff to prevent face burnout. "
        "Bright pixels in subject may exceed ceiling.",
        logger_prefix,
    )
    return None
