"""Postprocess — объединённый шаг: shadow_floor + stone_gamma + white_ceiling.

Этот модуль объединяет три финальные коррекции в один numpy-проход,
избегая множественных PIL↔numpy конверсий.

Порядок операций:
1. Shadow floor (impact — full subject, laser — face_mask only)
2. Stone gamma (SOP 5.1)
3. White ceiling с soft rolloff (по highlights-зоне или subject)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from retouch.processing.correction.mask_utils import clamp_masked
from retouch.processing.correction.gamma import apply_stone_gamma_masked
from retouch.processing.correction.rolloff import soft_rolloff_masked

if TYPE_CHECKING:
    from retouch.processing.analysis.zones import ZoneMasks

logger = logging.getLogger(__name__)


def apply_postprocess(
    img: Image.Image,
    subject_mask: np.ndarray,
    face_mask: np.ndarray | None,
    zone_masks: ZoneMasks | None,
    machine_type: str,
    shadow_floor: int = 0,
    stone_gamma: float | None = None,
    white_ceiling: int | None = None,
    compression: float = 0.35,
) -> Image.Image:
    """Применить финальные коррекции в одном numpy-проходе.

    Args:
        img: изображение после unsharp + shadow_noise
        subject_mask: маска субъекта (uint8)
        face_mask: маска лица (uint8) или None
        zone_masks: ZoneMasks для highlights-зоны или None
        machine_type: "laser_standard", "laser_80w", или "impact"
        shadow_floor: минимальный уровень теней (0 = отключён)
        stone_gamma: gamma камня (None или 1.0 = отключена)
        white_ceiling: потолок яркости (None = отключён)
        compression: compression ratio для soft rolloff

    Returns:
        Обработанное изображение.
    """
    needs_numpy = (
        (shadow_floor > 0)
        or (stone_gamma is not None and stone_gamma != 1.0)
        or (white_ceiling is not None)
    )

    if not needs_numpy:
        return img

    arr = np.array(img, dtype=np.float32)
    mask_bool = np.array(subject_mask) > 128

    # 1. Shadow floor
    if shadow_floor > 0:
        if machine_type == "impact":
            arr = clamp_masked(arr, subject_mask, vmin=shadow_floor, mask_bool=mask_bool)
            logger.info("Shadow floor applied: %d (impact, full subject)", shadow_floor)
        else:
            # laser_standard, laser_80w — только в зоне лица
            if face_mask is not None:
                face_mask_bool = np.array(face_mask) > 128
                floor_mask = mask_bool & face_mask_bool
                if floor_mask.any():
                    arr[floor_mask] = np.maximum(arr[floor_mask], float(shadow_floor))
                    logger.info(
                        "Shadow floor applied: %d (laser, face_mask only, %d px)",
                        shadow_floor, int(floor_mask.sum()),
                    )
                else:
                    logger.info("Shadow floor skipped: no face_mask overlap")
            else:
                logger.warning("Shadow floor skipped for laser: face_mask unavailable")

    # 2. Stone gamma (SOP 5.1)
    if stone_gamma is not None and stone_gamma != 1.0:
        arr = apply_stone_gamma_masked(arr, mask_bool, gamma=stone_gamma)
        logger.info("Stone gamma applied: %.2f", stone_gamma)

    # 3. White ceiling clamp ПОСЛЕ gamma — gamma < 1.0 осветляет
    if white_ceiling is not None:
        knee = white_ceiling * 0.90
        if zone_masks is not None and zone_masks.highlights.any():
            base = zone_masks.highlights > 128 if zone_masks.highlights.dtype != bool else zone_masks.highlights
            face = zone_masks.face_skin > 128 if zone_masks.face_skin.dtype != bool else zone_masks.face_skin
            rolloff_mask = (base | face).astype(np.uint8) * 255
            logger.info(
                "White ceiling rolloff applied to highlights+face_skin zone (%d px)",
                int(rolloff_mask.sum()),
            )
        else:
            rolloff_mask = np.array(subject_mask, dtype=np.uint8)
        arr = soft_rolloff_masked(
            arr, rolloff_mask, knee, float(white_ceiling), compression
        )
        logger.info(
            "White ceiling rolloff (post-gamma): %d, compression=%.2f",
            white_ceiling, compression,
        )

    return Image.fromarray(arr.astype(np.uint8))
