"""Тесты mask_utils — clamp_masked и утилиты масок."""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.mask_utils import clamp_masked


class TestClampMaskedVmin:
    """clamp_masked клиппит отрицательные значения (vmin=0 по умолчанию)."""

    def test_clamp_masked_clips_negative(self):
        """Отрицательные значения обрезаются до vmin=0."""
        arr = np.array([[-10, -1, 50, 200, 300]], dtype=np.float32)
        mask = Image.new("L", (5, 1), 255)
        result = clamp_masked(arr, mask, vmin=0, vmax=255)
        assert result.min() >= 0, f"Отрицательные не обрезаны: min={result.min()}"

    def test_clamp_masked_default_vmin_is_zero(self):
        """По умолчанию vmin=0 (не None)."""
        arr = np.array([[-5, 100, 260]], dtype=np.float32)
        mask = Image.new("L", (3, 1), 255)
        result = clamp_masked(arr.reshape(1, 3), mask, vmax=250)
        assert result.flatten()[0] >= 0, "vmin=0 по умолчанию"

    def test_clamp_masked_outside_mask_unchanged(self):
        """Пиксели вне маски не меняются."""
        arr = np.array([[-10, 100, 300]], dtype=np.float32)
        mask_arr = np.array([[0, 255, 0]], dtype=np.uint8)
        mask = Image.fromarray(mask_arr)
        result = clamp_masked(arr.reshape(1, 3), mask, vmin=0, vmax=250)
        flat = result.flatten()
        assert flat[0] == -10.0, "Фон не должен меняться (vmin)"
        assert flat[2] == 300.0, "Фон не должен меняться (vmax)"
        assert flat[1] == 100.0, "Субъект в диапазоне — не меняется"
