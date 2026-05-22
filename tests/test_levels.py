"""Тесты модуля levels — deprecated wrapper apply_levels."""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.correction.levels import (
    apply_levels,
)


class TestApplyLevels:
    """Тесты коррекции яркости (deprecated wrapper)."""

    def test_brightness_1_is_neutral(self):
        """brightness_factor=1.0 не меняет изображение."""
        arr = np.random.randint(50, 200, (100, 100), dtype=np.uint8)
        img = Image.fromarray(arr)
        result = apply_levels(img, 1.0)
        result_arr = np.array(result)
        diff = np.abs(result_arr.astype(int) - arr.astype(int))
        assert diff.max() <= 1, "brightness=1.0 не должен менять изображение"

    def test_brightness_increases_values(self):
        """brightness_factor>1.0 увеличивает яркость."""
        img = Image.new("L", (100, 100), 100)
        result = apply_levels(img, 1.5)
        result_val = np.array(result).mean()
        assert result_val > 100, f"Яркость должна увеличиться, а не {result_val:.0f}"

    def test_brightness_decreases_values(self):
        """brightness_factor<1.0 уменьшает яркость."""
        img = Image.new("L", (100, 100), 100)
        result = apply_levels(img, 0.5)
        result_val = np.array(result).mean()
        assert result_val < 100, f"Яркость должна уменьшиться, а не {result_val:.0f}"


class TestMaskProtection:
    """P6: масочная защита — фон не меняется при коррекции."""

    def test_levels_preserves_background_with_mask(self):
        """Levels с mask не меняет фоновые пиксели."""
        arr = np.full((100, 100), 128, dtype=np.uint8)
        mask_arr = np.zeros((100, 100), dtype=np.uint8)
        arr[30:70, 30:70] = 180
        mask_arr[30:70, 30:70] = 255
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)
        result = apply_levels(img, brightness_factor=1.3, subject_mask=mask)
        result_arr = np.array(result)
        assert result_arr[10, 10] == 128, f"Фон изменился: {result_arr[10, 10]}"
        assert result_arr[50, 50] > 180, f"Субъект не осветлился: {result_arr[50, 50]}"

    def test_levels_without_mask_backward_compat(self):
        """Levels без mask работает как раньше (глобальный enhance)."""
        img = Image.new("L", (100, 100), 128)
        result = apply_levels(img, brightness_factor=1.18)
        arr = np.array(result)
        assert arr[50, 50] > 128


class TestAdaptiveLevels:
    """Адаптивный bounded delta через deprecated wrapper."""

    def test_bright_input_no_clipping(self):
        """Яркий вход (median=211) — delta = 0 (в диапазоне), без изменений."""
        analytics = {
            'median_brightness': 211.0,
            'p90_brightness': 240.0,
        }
        img = Image.new("L", (100, 100), 211)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        result_arr = np.array(result)
        assert result_arr.max() < 255, "Клиппинг при ярком входе"

    def test_dark_input_gets_brightened(self):
        """Тёмный вход (median=80) — delta > 0, осветление."""
        analytics = {
            'median_brightness': 80.0,
            'p90_brightness': 150.0,
        }
        img = Image.new("L", (100, 100), 80)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        assert np.array(result).mean() > 80

    def test_overbright_input_gets_darkened(self):
        """Сверхъяркий вход (median=240) — delta < 0, затемнение."""
        analytics = {
            'median_brightness': 240.0,
            'p90_brightness': 252.0,
        }
        img = Image.new("L", (100, 100), 240)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        assert np.array(result).mean() <= 240

    def test_clipping_protection(self):
        """median выше target_max → delta < 0, затемнение."""
        analytics = {
            'median_brightness': 250.0,
            'p90_brightness': 252.0,
        }
        img = Image.new("L", (100, 100), 250)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        result_arr = np.array(result)
        assert result_arr.mean() < 250, "median выше target_max должна затемняться"

    def test_laser_80w_lower_target(self):
        """Laser 80W: target_min=160, target_max=180."""
        analytics = {
            'median_brightness': 190.0,
            'p90_brightness': 220.0,
        }
        result_laser = apply_levels(
            Image.new("L", (100, 100), 190),
            analytics=analytics, machine_type='laser_standard',
        )
        result_80w = apply_levels(
            Image.new("L", (100, 100), 190),
            analytics=analytics, machine_type='laser_80w',
        )
        assert np.array(result_80w).mean() < 190  # затемнение
        assert np.array(result_laser).mean() >= 190  # осветление или без изменений
