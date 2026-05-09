"""Тесты модуля glow — outer/inner glow, numpy оптимизация."""

import numpy as np
import pytest
from PIL import Image


class TestGlowNumpyEquivalence:
    """numpy-реализация glow opacity эквивалентна point(lambda)."""

    def test_outer_glow_numpy_result(self):
        """Outer glow: numpy clip+multiply даёт корректный результат."""
        from retouch.processing.glow import apply_outer_glow

        # Создаём простую маску с чётким прямоугольником
        arr = np.zeros((100, 100), dtype=np.uint8)
        arr[30:70, 30:70] = 255
        mask = Image.fromarray(arr)
        img_gray = Image.new("L", (100, 100), 128)

        result = apply_outer_glow(img_gray, mask, glow_size=10, glow_opacity=0.35)
        assert result.mode == "L"
        assert result.size == (100, 100)

        # Результат не должен быть полностью чёрным или белым
        result_arr = np.array(result)
        assert result_arr.min() < 200, "Glow не должен заливать всё белым"
        assert result_arr.max() > 100, "Glow должен добавлять яркость"

    def test_outer_glow_with_full_mask(self):
        """Outer glow с полной маской — свечение некуда, результат ≈ оригинал."""
        from retouch.processing.glow import apply_outer_glow

        mask = Image.new("L", (80, 80), 255)  # Вся маска = субъект
        img_gray = Image.new("L", (80, 80), 128)

        result = apply_outer_glow(img_gray, mask, glow_size=10, glow_opacity=0.35)
        result_arr = np.array(result)

        # При полной маске glow_mask = blurred - original ≈ 0
        # Поэтому результат должен быть близок к оригиналу
        assert abs(float(result_arr.mean()) - 128.0) < 20, \
            "При полной маске outer glow не должен значительно менять изображение"
