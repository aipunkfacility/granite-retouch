"""Тесты модуля преданализа — analyze_input() (P1, этап 7)."""

import pytest
import numpy as np
from PIL import Image

from retouch.processing.analysis import analyze_input


def _make_synthetic(face_value: int, bg_value: int = 0,
                    size: int = 200) -> tuple:
    """Создаёт синтетическое grayscale-изображение + маску."""
    img_arr = np.full((size, size), bg_value, dtype=np.uint8)
    mask = np.zeros((size, size), dtype=np.uint8)
    # Субъект — центральная область
    img_arr[50:150, 50:150] = face_value
    mask[50:150, 50:150] = 255
    return Image.fromarray(img_arr), mask


def _make_gradient(face_low: int, face_high: int,
                   bg_value: int = 0) -> tuple:
    """Создаёт градиентное изображение для тестирования тонального диапазона."""
    img_arr = np.full((200, 200), bg_value, dtype=np.uint8)
    mask = np.zeros((200, 200), dtype=np.uint8)
    gradient = np.linspace(face_low, face_high, 100 * 100).reshape(100, 100).astype(np.uint8)
    img_arr[50:150, 50:150] = gradient
    mask[50:150, 50:150] = 255
    return Image.fromarray(img_arr), mask


class TestAnalyzeInput:
    """P1: модуль преданализа — метрики и классификация."""

    def test_overbright_input(self):
        """median > 220 → input_class='overbright'."""
        img, mask = _make_synthetic(230)
        result = analyze_input(img, mask)
        assert result['input_class'] == 'overbright'
        assert result['median_brightness'] > 220

    def test_dark_input(self):
        """median < 120 → input_class='dark'."""
        img, mask = _make_synthetic(80)
        result = analyze_input(img, mask)
        assert result['input_class'] == 'dark'
        assert result['median_brightness'] < 120

    def test_medium_input(self):
        """120 < median < 180 → input_class='medium'."""
        img, mask = _make_synthetic(150)
        result = analyze_input(img, mask)
        assert result['input_class'] == 'medium'
        assert 120 < result['median_brightness'] < 180

    def test_bright_class(self):
        """180 < median < 220 → input_class='bright'."""
        img, mask = _make_synthetic(200)
        result = analyze_input(img, mask)
        assert result['input_class'] == 'bright'

    def test_tonal_range(self):
        """tonal_range = p90 - p10."""
        img, mask = _make_gradient(100, 220)
        result = analyze_input(img, mask)
        assert result['tonal_range'] > 0
        # p90 > p10
        assert result['p90_brightness'] > result['p10_brightness']
        # tonal_range совпадает с разницей
        assert abs(result['tonal_range'] -
                   (result['p90_brightness'] - result['p10_brightness'])) < 1

    def test_highlight_clipping(self):
        """highlight_clipping_pct > 0 при пикселях ≥250."""
        img_arr = np.full((200, 200), 0, dtype=np.uint8)
        mask = np.zeros((200, 200), dtype=np.uint8)
        # 50% субъекта — 255, 50% — 200
        img_arr[50:100, 50:150] = 255
        img_arr[100:150, 50:150] = 200
        mask[50:150, 50:150] = 255
        img = Image.fromarray(img_arr)
        result = analyze_input(img, mask)
        assert result['highlight_clipping_pct'] > 0

    def test_bg_metrics_after_chromakey(self):
        """После хромакея bg_median ≈ 0, subject_separation > 0."""
        img, mask = _make_synthetic(180, bg_value=0)
        result = analyze_input(img, mask)
        assert result['bg_median_brightness'] < 5
        assert result['subject_separation'] > 100

    def test_empty_bg(self):
        """bg_median=0 при маске без фоновых пикселей (всё — субъект)."""
        img_arr = np.full((200, 200), 180, dtype=np.uint8)
        mask = np.full((200, 200), 255, dtype=np.uint8)  # Всё — субъект
        img = Image.fromarray(img_arr)
        result = analyze_input(img, mask)
        assert result['bg_median_brightness'] == 0

    def test_scale_invariance(self):
        """Результаты идентичны при уменьшении (768px preview)."""
        img, mask = _make_gradient(100, 230)
        result_full = analyze_input(img, mask)

        # Уменьшаем до 200px
        img_small = img.resize((200, 200), Image.LANCZOS)
        mask_img = Image.fromarray(mask).resize((200, 200), Image.NEAREST)
        result_small = analyze_input(img_small, np.array(mask_img))

        # Медиана и перцентили в пределах ±2 ед.
        assert abs(result_full['median_brightness'] -
                   result_small['median_brightness']) <= 2
        assert abs(result_full['p90_brightness'] -
                   result_small['p90_brightness']) <= 2
