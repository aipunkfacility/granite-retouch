"""Тесты для модуля metrics.py — ZoneMetrics, StepMetricsRecord."""

import numpy as np
import pytest

from retouch.processing.metrics import (
    ZoneMetrics,
    StepMetricsRecord,
    compute_zone_metrics,
    make_step_record,
)


class TestZoneMetricsDataclass:
    """ZoneMetrics dataclass существует и имеет все поля."""

    def test_zone_metrics_dataclass_fields(self):
        """Все 7 полей присутствуют."""
        zm = ZoneMetrics(
            median=128.0, p10=50.0, p90=200.0, p95=220.0,
            max=255.0, variance=100.0, clipped_pct=1.5,
        )
        assert zm.median == 128.0
        assert zm.p10 == 50.0
        assert zm.p90 == 200.0
        assert zm.p95 == 220.0
        assert zm.max == 255.0
        assert zm.variance == 100.0
        assert zm.clipped_pct == 1.5


class TestStepMetricsRecordDataclass:
    """StepMetricsRecord dataclass существует и имеет все поля."""

    def test_step_metrics_record_dataclass_fields(self):
        """Все 4 поля присутствуют."""
        smr = StepMetricsRecord(
            step_name="levels",
            timestamp_ms=1000,
            zone_metrics={"face_skin": ZoneMetrics(128, 50, 200, 220, 255, 100, 1.5)},
            warnings=["test warning"],
        )
        assert smr.step_name == "levels"
        assert smr.timestamp_ms == 1000
        assert "face_skin" in smr.zone_metrics
        assert len(smr.warnings) == 1


class TestComputeZoneMetrics:
    """compute_zone_metrics корректно считает метрики."""

    def test_compute_zone_metrics_basic(self):
        """Базовый расчёт метрик для одной зоны."""
        arr = np.full((10, 10), 128.0, dtype=np.float32)
        mask = np.ones((10, 10), dtype=np.uint8) * 255

        result = compute_zone_metrics(arr, {"test": mask})
        assert "test" in result
        assert result["test"].median == 128.0

    def test_compute_zone_metrics_multiple_zones(self):
        """Метрики для нескольких зон."""
        arr = np.zeros((10, 10), dtype=np.float32)
        arr[:5, :] = 100.0
        arr[5:, :] = 200.0

        mask1 = np.zeros((10, 10), dtype=np.uint8)
        mask1[:5, :] = 255
        mask2 = np.zeros((10, 10), dtype=np.uint8)
        mask2[5:, :] = 255

        result = compute_zone_metrics(arr, {"zone1": mask1, "zone2": mask2})
        assert result["zone1"].median == 100.0
        assert result["zone2"].median == 200.0

    def test_missing_zone_is_absent_key_not_none(self):
        """Отсутствующая зона = отсутствие ключа, не None."""
        arr = np.zeros((10, 10), dtype=np.float32)
        mask = np.zeros((10, 10), dtype=np.uint8)

        result = compute_zone_metrics(arr, {"empty": mask})
        assert "empty" not in result

    def test_compute_zone_metrics_clipped_pct(self):
        """clipped_pct считает пиксели >= white_ceiling."""
        arr = np.zeros((10, 10), dtype=np.float32)
        arr[:5, :] = 255.0  # 50% clipped
        arr[5:, :] = 200.0  # 50% not clipped
        mask = np.ones((10, 10), dtype=np.uint8) * 255

        result = compute_zone_metrics(arr, {"test": mask}, white_ceiling=250)
        assert result["test"].clipped_pct == 50.0

    def test_compute_zone_metrics_variance(self):
        """variance корректно считается."""
        arr = np.array([[100, 200], [100, 200]], dtype=np.float32)
        mask = np.ones((2, 2), dtype=np.uint8) * 255

        result = compute_zone_metrics(arr, {"test": mask})
        assert result["test"].variance > 0


class TestMakeStepRecord:
    """make_step_record создаёт корректную запись."""

    def test_make_step_record_basic(self):
        """Базовое создание записи."""
        zm = ZoneMetrics(128, 50, 200, 220, 255, 100, 1.5)
        record = make_step_record("levels", {"face_skin": zm})
        assert record.step_name == "levels"
        assert record.timestamp_ms > 0
        assert "face_skin" in record.zone_metrics

    def test_make_step_record_with_warnings(self):
        """Запись с warnings."""
        record = make_step_record("levels", {}, ["warning1", "warning2"])
        assert len(record.warnings) == 2
