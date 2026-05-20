"""Тесты gamma-коррекции для компенсации потемнения на камне.

Камень (гранит/габбро) темнит изображение: белая точка на камне ≈ 85-95%
от исходной. Gamma < 1.0 поднимает тени, не трогая света — в отличие от
линейного brightness, который давил и тени и света одновременно.
"""

import numpy as np
import pytest

from retouch.processing.correction.gamma import apply_stone_gamma, apply_stone_gamma_masked


class TestStoneGammaCorrection:
    """Gamma-коррекция: компенсация потемнения на камне."""

    def test_gamma_below_one_brightens_shadows(self):
        """Gamma < 1.0 поднимает тени (SOP 5.1)."""
        arr = np.array([30, 80, 128, 200, 250], dtype=np.float32)
        result = apply_stone_gamma(arr, gamma=0.85)
        # Тени подняты
        assert result[0] > 30, f"Тень должна быть поднята: {result[0]:.0f}"
        assert result[1] > 80, f"Средняя тень поднята: {result[1]:.0f}"
        # Белая точка почти не сдвинулась
        assert result[4] >= 248, f"Белая точка стабильна: {result[4]:.0f}"

    def test_gamma_1_is_identity(self):
        """Gamma=1.0 — нейтральная (ничего не меняется)."""
        arr = np.array([50, 128, 200], dtype=np.float32)
        result = apply_stone_gamma(arr, gamma=1.0)
        np.testing.assert_array_almost_equal(result, arr, decimal=1)

    def test_gamma_only_inside_mask(self):
        """Gamma применяется только внутри маски субъекта."""
        arr = np.full((100, 100), 80, dtype=np.float32)
        mask = np.zeros((100, 100), dtype=bool)
        mask[25:75, 25:75] = True  # субъект — квадрат в центре
        result = apply_stone_gamma_masked(arr, mask, gamma=0.85)
        # Вне маски — не изменилось
        assert result[10, 10] == 80.0, "Фон не должен меняться"
        # Внутри маски — поднялось
        assert result[50, 50] > 80.0, "Субъект должен осветлиться"

    def test_gamma_preserves_range(self):
        """Результат gamma в [0, 255]."""
        arr = np.array([0, 1, 127, 255], dtype=np.float32)
        result = apply_stone_gamma(arr, gamma=0.80)
        assert result.min() >= 0 and result.max() <= 255

    def test_gamma_monotonic(self):
        """Gamma сохраняет монотонность: если a < b то gamma(a) < gamma(b)."""
        arr = np.array([10, 50, 100, 150, 200, 240], dtype=np.float32)
        result = apply_stone_gamma(arr, gamma=0.85)
        for i in range(len(result) - 1):
            assert result[i] < result[i + 1], \
                f"Нарушена монотонность: gamma({arr[i]:.0f})={result[i]:.1f} >= gamma({arr[i+1]:.0f})={result[i+1]:.1f}"
