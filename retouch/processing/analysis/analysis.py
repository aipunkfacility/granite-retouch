"""Модуль преданализа входного grayscale-изображения."""

import logging
from dataclasses import dataclass, asdict, field

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ZoneAnalytics:
    """Метрики одной зоны (face_skin, face_dark, hair и т.д.)."""
    median: float = 0.0
    p10: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    max: float = 0.0
    variance: float = 0.0
    clipped_pct: float = 0.0


@dataclass
class ImageAnalytics:
    """Структурированные метрики входного изображения (B.3).

    Поля совпадают с ключами dict из analyze_input() — обратная
    совместимость: from_dict(старый_dict).to_dict() == старый_dict.
    """
    median_brightness: float = 0.0
    mean_brightness: float = 0.0
    p10_brightness: float = 0.0
    p25_brightness: float = 0.0
    p75_brightness: float = 0.0
    p90_brightness: float = 0.0
    tonal_range: float = 0.0
    highlight_clipping_pct: float = 0.0
    shadow_clipping_pct: float = 0.0
    bg_median_brightness: float = 0.0
    bg_mean_brightness: float = 0.0
    subject_separation: float = 0.0
    input_class: str = 'dark'
    per_zone: dict[str, ZoneAnalytics] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "ImageAnalytics":
        """Создать из dict (обратная совместимость)."""
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        if "per_zone" in known and isinstance(known["per_zone"], dict):
            known["per_zone"] = {
                k: ZoneAnalytics(**v) if isinstance(v, dict) else v
                for k, v in known["per_zone"].items()
            }
        return cls(**known)

    def to_dict(self) -> dict:
        """Конвертировать в dict (обратная совместимость)."""
        d = asdict(self)
        if self.per_zone:
            d["per_zone"] = {
                k: asdict(v) for k, v in self.per_zone.items()
            }
        return d


def analyze_input(gray_image: Image.Image, subject_mask: np.ndarray,
                  face_mask: np.ndarray | None = None,
                  zone_masks: object | None = None) -> dict:
    """Измеряет тональные характеристики входного grayscale-файла.

    Вызывается ОДИН раз после шага 2 (Grayscale), когда доступны
    grayscale-изображение и subject_mask.
    Результат передаётся во все последующие шаги.

    FIX-ORD-007: Если передан face_mask — метрики (median, p90, p95)
    считаются по лицу, а не по всему субъекту. Иначе чёрная одежда
    тянет медиану вниз и levels factor получается безумным (13x).

    Args:
        gray_image: PIL.Image в режиме L (grayscale)
        subject_mask: numpy array — маска субъекта (bool или 0/255)
        face_mask: numpy array — маска лица (bool или 0/255).
            Если None — метрики считаются по subject_mask (legacy).
        zone_masks: ZoneMasks или None. Если передан — добавляет
            per-zone метрики в поле per_zone результата.

    Returns:
        dict с метриками для адаптивных доработок пайплайна.
    """
    img_arr = np.array(gray_image, dtype=np.float32)

    # Нормализуем маску в bool
    if subject_mask.dtype != bool:
        subj_bool = np.array(subject_mask) > 128
    else:
        subj_bool = subject_mask

    # FIX-ORD-007: для метрик яркости используем лицо, если есть
    if face_mask is not None:
        if face_mask.dtype != bool:
            face_bool = np.array(face_mask) > 128
        else:
            face_bool = face_mask
        metric_pixels = img_arr[face_bool & subj_bool]
    else:
        metric_pixels = img_arr[subj_bool]

    bg_pixels = img_arr[~subj_bool]

    if len(metric_pixels) == 0:
        logger.warning("analyze_input: нет пикселей для анализа")
        return _empty_result()

    # PERF: batch np.percentile — 1 вызов вместо 6
    p10, p25, p75, p90, p95 = np.percentile(metric_pixels, [10, 25, 75, 90, 95])

    result = {
        # Основные метрики (лицо при наличии face_mask, иначе субъект)
        'median_brightness': float(np.median(metric_pixels)),
        'mean_brightness': float(np.mean(metric_pixels)),

        # Тональный диапазон
        'p10_brightness': float(p10),
        'p25_brightness': float(p25),
        'p75_brightness': float(p75),
        'p90_brightness': float(p90),
        'p95_brightness': float(p95),
        'tonal_range': float(p90 - p10),

        # Проблемные зоны
        'highlight_clipping_pct': float(np.sum(metric_pixels >= 250) / len(metric_pixels) * 100),
        'shadow_clipping_pct': float(np.sum(metric_pixels <= 5) / len(metric_pixels) * 100),

        # Метрики фона (для P3: адаптивный glow)
        'bg_median_brightness': float(np.median(bg_pixels)) if len(bg_pixels) > 0 else 0,
        'bg_mean_brightness': float(np.mean(bg_pixels)) if len(bg_pixels) > 0 else 0,
        'subject_separation': float(abs(np.median(metric_pixels) - (np.median(bg_pixels) if len(bg_pixels) > 0 else 0))),

        # Классификация входа
        'input_class': _classify_input(metric_pixels),
    }

    # Per-zone метрики (v6.5)
    if zone_masks is not None and hasattr(zone_masks, "face_skin"):
        zp = {}
        for zone_name in ("face_skin", "face_dark", "hair", "clothes", "highlights"):
            zmask = getattr(zone_masks, zone_name, None)
            if zmask is None:
                continue
            zarr = zmask.astype(bool) if zmask.dtype != bool else zmask
            zpx = img_arr[zarr]
            if len(zpx) < 10:
                continue
            z95 = float(np.percentile(zpx, 95))
            zp[zone_name] = {
                "median": float(np.median(zpx)),
                "p10": float(np.percentile(zpx, 10)),
                "p90": float(np.percentile(zpx, 90)),
                "p95": z95,
                "max": float(zpx.max()),
                "variance": float(np.var(zpx)),
                "clipped_pct": float(np.sum(zpx >= 250) / len(zpx) * 100),
            }
        if zp:
            result["per_zone"] = zp

    logger.info(
        "Input analysis: median=%.1f, class=%s, range=%.1f, p90=%.1f, p95=%.1f, clipping=%.1f%%",
        result['median_brightness'], result['input_class'],
        result['tonal_range'], result['p90_brightness'],
        result['p95_brightness'], result['highlight_clipping_pct'],
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
        'p75_brightness': 0, 'p90_brightness': 0, 'p95_brightness': 0,
        'tonal_range': 0,
        'highlight_clipping_pct': 0, 'shadow_clipping_pct': 0,
        'bg_median_brightness': 0, 'bg_mean_brightness': 0,
        'subject_separation': 0,
        'input_class': 'dark',
        'per_zone': {},
    }
