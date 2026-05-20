"""Тесты инвариантов shadow noise: влияние на маску и уровни."""

import numpy as np
from PIL import Image
import pytest
from retouch.processing.correction.shadow_noise import add_shadow_noise


class TestShadowNoiseInvariants:
    @pytest.fixture
    def gray_gradient(self):
        """Градиент от 0 до 100 для проверки порога шума."""
        arr = np.linspace(0, 100, 512).reshape(1, 512).repeat(100, axis=0)
        return Image.fromarray(arr.astype(np.uint8))

    def test_noise_is_deterministic(self, gray_gradient):
        """Шум должен быть детерминированным при одинаковом seed (внутри функции)."""
        res1 = add_shadow_noise(gray_gradient, Image.new("L", gray_gradient.size, 255), noise_min=10, noise_max=20, shadow_threshold=50)
        res2 = add_shadow_noise(gray_gradient, Image.new("L", gray_gradient.size, 255), noise_min=10, noise_max=20, shadow_threshold=50)
        assert np.array_equal(np.array(res1), np.array(res2)), "Шум должен быть детерминированным"

    def test_noise_threshold(self, gray_gradient):
        """Шум не должен затрагивать пиксели выше порога shadow_threshold."""
        threshold = 50
        res = add_shadow_noise(gray_gradient, Image.new("L", gray_gradient.size, 255), noise_min=10, noise_max=20, shadow_threshold=threshold)
        arr_res = np.array(res)
        arr_orig = np.array(gray_gradient)
        
        # Пиксели выше порога (с запасом на плавность если она есть, но здесь порог жесткий)
        mask_above = arr_orig > threshold
        assert np.all(arr_res[mask_above] == arr_orig[mask_above]), "Шум не должен менять пиксели выше порога"

    def test_noise_range(self, gray_gradient):
        """Шум должен быть в заданном диапазоне [noise_min, noise_max]."""
        noise_min, noise_max = 5, 15
        threshold = 50
        res = add_shadow_noise(gray_gradient, Image.new("L", gray_gradient.size, 255), noise_min=noise_min, noise_max=noise_max, shadow_threshold=threshold)
        arr_res = np.array(res)
        arr_orig = np.array(gray_gradient)
        
        # Пиксели ниже порога должны быть в диапазоне шума
        mask_below = arr_orig < threshold
        vals_below = arr_res[mask_below]
        
        assert np.all(vals_below >= noise_min), f"Шум ниже {noise_min}"
        assert np.all(vals_below <= noise_max), f"Шум выше {noise_max}"

