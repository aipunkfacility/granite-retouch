"""Step metrics — сбор метрик по зонам после каждого шага пайплайна.

ZoneMetrics: метрики одной зоны (median, p10, p90, p95, max, variance, clipped_pct).
StepMetricsRecord: запись метрик после конкретного шага.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ZoneMetrics:
    """Метрики одной зоны."""
    median: float
    p10: float
    p90: float
    p95: float
    max: float
    variance: float
    clipped_pct: float


@dataclass
class StepMetricsRecord:
    """Запись метрик после одного шага пайплайна."""
    step_name: str
    timestamp_ms: int
    zone_metrics: dict[str, ZoneMetrics] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def compute_zone_metrics(
    arr: np.ndarray,
    zone_masks: dict[str, np.ndarray],
    white_ceiling: int = 250,
) -> dict[str, ZoneMetrics]:
    """Посчитать метрики для каждой зоны.

    Args:
        arr: float array (H, W) — grayscale
        zone_masks: dict {zone_name: bool/uint8 mask}
        white_ceiling: порог клиппинга

    Returns:
        dict[str, ZoneMetrics]: метрики по зонам.
        Отсутствующие зоны — отсутствие ключа, не None.
    """
    result: dict[str, ZoneMetrics] = {}

    for name, mask in zone_masks.items():
        if mask.dtype == bool:
            mask_bool = mask
        elif mask.max() <= 1:
            # Binary mask with 0/1 values
            mask_bool = mask.astype(bool)
        else:
            # Standard 0-255 mask
            mask_bool = mask > 128
        pixels = arr[mask_bool]

        if len(pixels) == 0:
            continue

        p10, p90, p95 = np.percentile(pixels, [10, 90, 95])
        clipped = np.sum(pixels >= white_ceiling) / len(pixels) * 100

        result[name] = ZoneMetrics(
            median=float(np.median(pixels)),
            p10=float(p10),
            p90=float(p90),
            p95=float(p95),
            max=float(np.max(pixels)),
            variance=float(np.var(pixels)),
            clipped_pct=float(clipped),
        )

    return result


def make_step_record(
    step_name: str,
    zone_metrics: dict[str, ZoneMetrics],
    warnings: list[str] | None = None,
) -> StepMetricsRecord:
    """Создать StepMetricsRecord."""
    return StepMetricsRecord(
        step_name=step_name,
        timestamp_ms=int(time.monotonic() * 1000),
        zone_metrics=zone_metrics,
        warnings=warnings or [],
    )
