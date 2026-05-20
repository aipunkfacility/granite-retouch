"""Зональные маски и приоритизация для пайплайна обработки.

Модуль строит дизъюнктное разбиение изображения на технические зоны:
face_skin, face_dark, hair, clothes, highlights, contour_inner, contour_outer.

Все операции проектируются как batch numpy pass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ZoneMasks
# ---------------------------------------------------------------------------

@dataclass
class ZoneMasks:
    """Дизъюнктное разбиение изображения на технические зоны.

    Все маски — uint8 ndarray одинакового размера (H, W).
    После resolve_zone_priority() все final_* маски не пересекаются.
    """
    subject: np.ndarray       # subject_mask из chromakey
    face: np.ndarray          # face_mask из овала
    hair: np.ndarray          # hair_mask (approximate)
    face_skin: np.ndarray     # кожа лица
    face_dark: np.ndarray     # тёмные зоны внутри овала (волосы, борода, тени)
    clothes: np.ndarray       # одежда и фон внутри subject
    highlights: np.ndarray    # яркие зоны субъекта
    contour_inner: np.ndarray # внутренний край для glow
    contour_outer: np.ndarray # внешний край для антифринги
    background: np.ndarray    # фон (хромакей)

    # Метаданные
    beard_suspected: bool = False
    beard_reclassified_pixels: int = 0
    contour_fallback_used: bool = False


# ---------------------------------------------------------------------------
# Построение зон
# ---------------------------------------------------------------------------

def build_zone_masks(
    subject_mask: Image.Image,
    face_mask: Image.Image | None,
    img_gray: Image.Image,
    hair_mask: np.ndarray | None = None,
    chromakey_gradient: np.ndarray | None = None,
    skin_threshold: int = 100,
    highlight_threshold: int = 200,
    contour_gradient_threshold: float = 0.5,
    beard_dark_ratio: float = 0.40,
    beard_concentration: float = 0.60,
) -> ZoneMasks:
    """Построить ZoneMasks из входных данных.

    Args:
        subject_mask: PIL.Image (L) — маска субъекта
        face_mask: PIL.Image (L) или None — маска лица из овала
        img_gray: PIL.Image (L) — grayscale изображение
        hair_mask: numpy array или None — маска волос
        chromakey_gradient: float array (0..1) или None — градиент хромакея
        skin_threshold: абсолютный порог кожи (fallback)
        highlight_threshold: порог highlights
        contour_gradient_threshold: порог для contour из gradient
        beard_dark_ratio: доля face_dark для подозрения бороды
        beard_concentration: концентрация face_dark в нижней трети

    Returns:
        ZoneMasks: дизъюнктное разбиение

    Raises:
        ValueError: если face_mask не построен
    """
    gray_arr = np.array(img_gray, dtype=np.float32)
    subj = np.array(subject_mask, dtype=np.uint8)
    subj_bool = subj > 128

    if face_mask is None:
        raise ValueError(
            "face_mask не построен — пайплайн не может продолжить обработку. "
            "Проверьте входное изображение или задайте face_oval вручную."
        )

    face = np.array(face_mask, dtype=np.uint8)
    face_bool = face > 128

    # Hair mask
    if hair_mask is None:
        hair = np.zeros_like(subj_bool, dtype=np.uint8)
    else:
        hair = hair_mask.astype(np.uint8)

    # Adaptive skin threshold
    adaptive_threshold = _compute_adaptive_skin_threshold(
        gray_arr, face_bool, skin_threshold
    )

    # Базовые зоны (до приоритизации)
    face_skin_raw = face_bool & subj_bool & (gray_arr >= adaptive_threshold)
    face_dark_raw = face_bool & subj_bool & (gray_arr < adaptive_threshold)
    highlights_raw = subj_bool & (gray_arr >= highlight_threshold)

    # Beard detection и переклассификация
    beard_suspected = False
    beard_reclassified = 0
    face_dark_total = int(np.sum(face_dark_raw))
    face_total = int(np.sum(face_bool & subj_bool))

    if face_total > 0 and face_dark_total / face_total > beard_dark_ratio:
        # Spatial check: концентрация face_dark в нижней трети овала
        h = gray_arr.shape[0]
        face_bbox = _get_face_bbox(face_bool)
        if face_bbox is not None:
            _, y_max, _, _ = face_bbox
            lower_third_start = int(face_bbox[0] + (y_max - face_bbox[0]) * 2 / 3)
            lower_third_mask = np.zeros_like(face_bool)
            lower_third_mask[lower_third_start:, :] = True

            face_dark_lower = int(np.sum(face_dark_raw & lower_third_mask))
            face_lower = int(np.sum((face_bool & subj_bool) & lower_third_mask))

            if face_lower > 0 and face_dark_lower / face_lower > beard_concentration:
                beard_suspected = True
                # Переклассификация: face_dark → hair (только в нижней трети)
                reclass = face_dark_raw & lower_third_mask & (hair > 0).any()
                # Переклассифицируем только если hair_mask не пуста
                if hair.any():
                    reclass = face_dark_raw & lower_third_mask
                    face_dark_raw = face_dark_raw & ~reclass
                    hair = hair | reclass.astype(np.uint8)
                    beard_reclassified = int(np.sum(reclass))

    # Clothes
    clothes_raw = subj_bool & ~face_bool & ~(hair > 0)

    # Contour из chromakey gradient
    contour_inner_raw, contour_outer_raw, fallback_used = _build_contour_masks(
        chromakey_gradient, subj_bool, contour_gradient_threshold
    )

    # Background
    background = ~subj_bool

    # Разрешение приоритета
    final = resolve_zone_priority(
        highlights=highlights_raw.astype(np.uint8),
        face_skin=face_skin_raw.astype(np.uint8),
        face_dark=face_dark_raw.astype(np.uint8),
        hair=hair,
        clothes=clothes_raw.astype(np.uint8),
        contour_inner=contour_inner_raw.astype(np.uint8),
        contour_outer=contour_outer_raw.astype(np.uint8),
        background=background.astype(np.uint8),
    )

    logger.info(
        "ZoneMasks built: face_skin=%d, face_dark=%d, hair=%d, "
        "clothes=%d, highlights=%d, contour_inner=%d, beard=%s",
        int(np.sum(final.face_skin)),
        int(np.sum(final.face_dark)),
        int(np.sum(final.hair)),
        int(np.sum(final.clothes)),
        int(np.sum(final.highlights)),
        int(np.sum(final.contour_inner)),
        beard_suspected,
    )

    return ZoneMasks(
        subject=subj,
        face=face,
        hair=final.hair,
        face_skin=final.face_skin,
        face_dark=final.face_dark,
        clothes=final.clothes,
        highlights=final.highlights,
        contour_inner=final.contour_inner,
        contour_outer=final.contour_outer,
        background=final.background,
        beard_suspected=beard_suspected,
        beard_reclassified_pixels=beard_reclassified,
        contour_fallback_used=fallback_used,
    )


# ---------------------------------------------------------------------------
# Priority resolution
# ---------------------------------------------------------------------------

@dataclass
class _ResolvedZones:
    highlights: np.ndarray
    face_skin: np.ndarray
    face_dark: np.ndarray
    hair: np.ndarray
    clothes: np.ndarray
    contour_inner: np.ndarray
    contour_outer: np.ndarray
    background: np.ndarray


def resolve_zone_priority(
    highlights: np.ndarray,
    face_skin: np.ndarray,
    face_dark: np.ndarray,
    hair: np.ndarray,
    clothes: np.ndarray,
    contour_inner: np.ndarray,
    contour_outer: np.ndarray,
    background: np.ndarray,
) -> _ResolvedZones:
    """Разрешить пересечения зон по приоритету.

    Приоритет: highlights > face_skin > face_dark > hair > clothes > contour.

    Контракт: все выходные маски дизъюнктны (не пересекаются).
    contour_outer не участвует в subject-zone приоритизации — он вне subject_mask.

    Args:
        Все маски — uint8 ndarray одинакового размера.

    Returns:
        _ResolvedZones: дизъюнктное разбиение.
    """
    final_highlights = highlights

    final_face_skin = face_skin & ~final_highlights

    final_face_dark = face_dark & ~final_highlights & ~final_face_skin

    final_hair = hair & ~final_highlights & ~final_face_skin & ~final_face_dark

    final_clothes = (
        clothes & ~final_highlights & ~final_face_skin
        & ~final_face_dark & ~final_hair
    )

    final_contour_inner = (
        contour_inner & ~final_highlights & ~final_face_skin
        & ~final_face_dark & ~final_hair & ~final_clothes
    )

    final_contour_outer = contour_outer

    final_background = background

    return _ResolvedZones(
        highlights=final_highlights,
        face_skin=final_face_skin,
        face_dark=final_face_dark,
        hair=final_hair,
        clothes=final_clothes,
        contour_inner=final_contour_inner,
        contour_outer=final_contour_outer,
        background=final_background,
    )


# ---------------------------------------------------------------------------
# Adaptive skin threshold
# ---------------------------------------------------------------------------

def _compute_adaptive_skin_threshold(
    gray_arr: np.ndarray,
    face_bool: np.ndarray,
    absolute_skin_min: int = 100,
    delta: int = 15,
    min_value: int = 60,
    max_value: int = 180,
) -> float:
    """Двухпроходной адаптивный порог кожи.

    Pass 1: coarse_skin = face_pixels >= absolute_skin_min
    Pass 2: robust_face_center = histogram_mode(coarse_skin) со сглаживанием
    Result: clamp(robust_face_center - delta, min_value, max_value)

    Args:
        gray_arr: float array (H, W) — grayscale
        face_bool: bool array (H, W) — face mask
        absolute_skin_min: нижняя граница для coarse_skin
        delta: смещение от центра распределения
        min_value: минимальный порог
        max_value: максимальный порог

    Returns:
        float: адаптивный порог кожи
    """
    face_pixels = gray_arr[face_bool]

    if len(face_pixels) == 0:
        return float(absolute_skin_min)

    # Coarse skin: отфильтровать очень тёмные пиксели (брови, тени)
    coarse = face_pixels[face_pixels >= absolute_skin_min]

    if len(coarse) < 10:
        # Слишком мало пикселей — fallback на абсолютный порог
        return float(absolute_skin_min)

    # Histogram mode со сглаживанием
    hist = np.bincount(coarse.astype(np.uint8), minlength=256)

    # Сглаживание: convolution [0.25, 0.5, 0.25]
    smoothed = np.convolve(hist, [0.25, 0.5, 0.25], mode="same")

    mode_value = int(np.argmax(smoothed))

    threshold = mode_value - delta
    threshold = max(min(threshold, max_value), min_value)

    logger.debug(
        "Adaptive skin threshold: mode=%d, threshold=%d (delta=%d, abs_min=%d)",
        mode_value, threshold, delta, absolute_skin_min,
    )

    return float(threshold)


# ---------------------------------------------------------------------------
# Contour masks from chromakey gradient
# ---------------------------------------------------------------------------

def _build_contour_masks(
    gradient: np.ndarray | None,
    subj_bool: np.ndarray,
    threshold: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Построить contour_inner и contour_outer из градиента хромакея.

    Fallback: если gradient некачественная (>30% subject), используем
    morphological contour.

    Args:
        gradient: float array (H, W) 0..1 или None
        subj_bool: bool array (H, W)
        threshold: порог разделения inner/outer

    Returns:
        (contour_inner, contour_outer, fallback_used)
    """
    from scipy.ndimage import binary_dilation, binary_erosion

    if gradient is None:
        return _morphological_contour(subj_bool), np.zeros_like(subj_bool, dtype=np.uint8), True

    contour_inner = (gradient > threshold) & (gradient < 1.0)
    contour_outer = (gradient > 0.0) & (gradient <= threshold)

    # Fallback check
    subj_area = int(np.sum(subj_bool))
    inner_area = int(np.sum(contour_inner))

    if subj_area > 0 and inner_area / subj_area > 0.30:
        logger.warning(
            "Contour gradient некачественная: inner=%d (%.1f%% subject) > 30%%. "
            "Fallback на morphological contour.",
            inner_area, inner_area / subj_area * 100,
        )
        return _morphological_contour(subj_bool), np.zeros_like(subj_bool, dtype=np.uint8), True

    return contour_inner.astype(np.uint8), contour_outer.astype(np.uint8), False


def _morphological_contour(subj_bool: np.ndarray) -> np.ndarray:
    """Fallback: morphological contour через dilate - erode."""
    from scipy.ndimage import binary_dilation, binary_erosion

    dilated = binary_dilation(subj_bool, iterations=2)
    eroded = binary_erosion(subj_bool, iterations=2)
    return (dilated & ~eroded).astype(np.uint8)


def _get_face_bbox(face_bool: np.ndarray) -> tuple[int, int, int, int] | None:
    """Получить bbox face mask: (y_min, y_max, x_min, x_max)."""
    rows = np.any(face_bool, axis=1)
    cols = np.any(face_bool, axis=0)

    if not rows.any():
        return None

    y_min = int(np.argmax(rows))
    y_max = int(len(rows) - np.argmax(rows[::-1]))
    x_min = int(np.argmax(cols))
    x_max = int(len(cols) - np.argmax(cols[::-1]))

    return y_min, y_max, x_min, x_max
