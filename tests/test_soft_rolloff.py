"""Тесты для модуля rolloff.py — soft_rolloff_masked."""

import numpy as np
import pytest

from retouch.processing.rolloff import soft_rolloff_masked


class TestSoftRolloffMasked:
    """soft_rolloff_masked корректно сжимает света."""

    def test_soft_rolloff_masked_compresses_highlights(self):
        """Значения выше knee сжимаются."""
        arr = np.full((10, 10), 240.0, dtype=np.float32)
        mask = np.ones((10, 10), dtype=np.uint8) * 255

        result = soft_rolloff_masked(arr, mask, knee=225.0, ceiling=250.0, compression=0.35)
        # 240 > 225, excess = 15, compressed = 225 + 15*0.35 = 230.25
        assert result[0, 0] < 240.0
        assert result[0, 0] > 225.0

    def test_soft_rolloff_no_plateau(self):
        """Hard plateau не появляется на ceiling."""
        arr = np.array([[230, 240, 250], [235, 245, 255]], dtype=np.float32)
        mask = np.ones((2, 3), dtype=np.uint8) * 255

        result = soft_rolloff_masked(arr, mask, knee=225.0, ceiling=250.0, compression=0.35)
        # Значения должны быть разными, не plateau
        unique_vals = len(set(result.flatten()))
        assert unique_vals > 1

    def test_soft_rolloff_mask_applies_only_to_mask(self):
        """Пиксели вне маски не изменяются."""
        arr = np.full((10, 10), 240.0, dtype=np.float32)
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[:5, :] = 255

        result = soft_rolloff_masked(arr, mask, knee=225.0, ceiling=250.0)
        assert result[6, 0] == 240.0  # вне маски
        assert result[2, 0] < 240.0   # внутри маски

    def test_compression_from_config_not_hardcoded(self):
        """compression — параметр, не хардкод."""
        arr = np.full((10, 10), 240.0, dtype=np.float32)
        mask = np.ones((10, 10), dtype=np.uint8) * 255

        r1 = soft_rolloff_masked(arr.copy(), mask, knee=225.0, ceiling=250.0, compression=0.35)
        r2 = soft_rolloff_masked(arr.copy(), mask, knee=225.0, ceiling=250.0, compression=0.50)
        assert r1[0, 0] != r2[0, 0]

    def test_rolloff_vs_ceiling_precedence(self):
        """Rolloff заменяет hard ceiling, clip остаётся страховкой."""
        arr = np.full((10, 10), 260.0, dtype=np.float32)
        mask = np.ones((10, 10), dtype=np.uint8) * 255

        result = soft_rolloff_masked(arr, mask, knee=225.0, ceiling=250.0, compression=0.35)
        assert np.all(result <= 250.0)

    def test_soft_rolloff_empty_mask(self):
        """Пустая маска не меняет arr."""
        arr = np.full((10, 10), 240.0, dtype=np.float32)
        mask = np.zeros((10, 10), dtype=np.uint8)

        result = soft_rolloff_masked(arr, mask, knee=225.0, ceiling=250.0)
        assert np.allclose(result, 240.0)

    def test_soft_rolloff_values_below_knee_unchanged(self):
        """Значения ниже knee не изменяются."""
        arr = np.full((10, 10), 200.0, dtype=np.float32)
        mask = np.ones((10, 10), dtype=np.uint8) * 255

        result = soft_rolloff_masked(arr, mask, knee=225.0, ceiling=250.0)
        assert result[0, 0] == 200.0
