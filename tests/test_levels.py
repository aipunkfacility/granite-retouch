"""Тесты модуля levels — яркость, unsharp, контроль лица."""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.levels import (
    apply_levels,
    apply_unsharp_mask,
    check_face_brightness,
    _curves_correction,
    _shrink_mask,
)


class TestApplyLevels:
    """Тесты коррекции яркости."""

    def test_brightness_1_is_neutral(self):
        """brightness_factor=1.0 не меняет изображение."""
        arr = np.random.randint(50, 200, (100, 100), dtype=np.uint8)
        img = Image.fromarray(arr, "L")
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


class TestApplyUnsharpMask:
    """Тесты Unsharp Mask."""

    def test_sharpens_image(self):
        """Unsharp Mask добавляет резкость (разница с оригиналом)."""
        # Создаём плавный градиент
        arr = np.linspace(0, 255, 100 * 100, dtype=np.uint8).reshape(100, 100)
        img = Image.fromarray(arr, "L")
        result = apply_unsharp_mask(img)
        # Разница должна быть (резкость меняет градиент)
        diff = np.abs(np.array(result).astype(float) - arr.astype(float))
        assert diff.mean() > 0, "Unsharp Mask должен менять изображение"

    def test_output_is_l_mode(self):
        """Результат — grayscale (L)."""
        img = Image.new("L", (100, 100), 128)
        result = apply_unsharp_mask(img)
        assert result.mode == "L", f"Результат должен быть L, а не {result.mode}"


class TestCurvesCorrection:
    """Тесты нелинейной (curves) коррекции."""

    def test_shadows_get_full_correction(self):
        """Тёмные пиксели получают полную коррекцию."""
        arr = np.array([0, 10, 30, 50], dtype=np.float32)
        correction = 1.3
        result = _curves_correction(arr, correction)
        # Нулевой пиксель: 0 * 1.3 = 0, delta=0, result=0 — это правильно
        # Но пиксель 10: 10*1.3=13, delta=3, weight~1.0 → result≈13
        assert result[1] > 10, f"Тёмный пиксель должен стать ярче: {result[1]:.0f}"
        assert result[2] > 30, f"Пиксель 30 должен стать ярче: {result[2]:.0f}"
        assert result[3] > 50, f"Пиксель 50 должен стать ярче: {result[3]:.0f}"

    def test_highlights_get_minimal_correction(self):
        """Светлые пиксели (240+) корректируются минимально."""
        arr = np.array([240, 245, 250, 255], dtype=np.float32)
        correction = 1.3
        result = _curves_correction(arr, correction)
        # Curves-коррекция: на 240 weight~0.33, на 245 weight~0.17, на 250+ weight~0
        # diff = linear_correction * weight, где linear = pixel * (correction - 1)
        # 240: delta = 240*0.3=72, weight≈0.33, diff≈24 — ожидаемо
        diff = np.abs(result - arr)
        # Света корректируются МЕНЬШЕ чем тени — проверяем монотонность
        # Коррекция для 240 должна быть больше чем для 250
        assert diff[0] >= diff[2], "Чем светлее пиксель, тем меньше коррекция"
        # И коррекция для 250+ минимальна
        assert diff[2] < diff[1], "250 корректируется меньше чем 245"

    def test_output_clipped(self):
        """Результат в диапазоне 0–255."""
        arr = np.array([250, 252, 254, 255], dtype=np.float32)
        result = _curves_correction(arr, 1.5)
        assert result.min() >= 0 and result.max() <= 255


class TestShrinkMask:
    """Тесты сжатия маски (для исключения glow-зоны)."""

    def test_shrinks_mask(self):
        """Маска сжимается на заданное число пикселей."""
        # Квадратная маска 100x100
        mask = Image.new("L", (100, 100), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([10, 10, 89, 89], fill=255)

        result = _shrink_mask(mask, shrink_px=5)
        result_arr = np.array(result)

        # Сжатая маска должна иметь меньше белых пикселей
        original_white = (np.array(mask) > 128).sum()
        shrunk_white = (result_arr > 128).sum()
        assert shrunk_white < original_white, \
            "Сжатая маска должна быть меньше оригинала"

    def test_small_shrink_reduces_mask(self):
        """Малое сжатие (3px) немного уменьшает маску."""
        mask = Image.new("L", (100, 100), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([10, 10, 89, 89], fill=255)
        original_white = (np.array(mask) > 128).sum()
        result = _shrink_mask(mask, shrink_px=3)
        result_white = (np.array(result) > 128).sum()
        assert result_white < original_white, \
            "Маска должна уменьшиться после сжатия"
        # Но не слишком сильно — 3px с каждой стороны
        assert result_white > original_white * 0.5, \
            "Маска не должна уменьшиться больше чем вдвое"


class TestCheckFaceBrightness:
    """Тесты контроля яркости лица."""

    def test_dark_face_gets_brightened(self):
        """Тёмное лицо (среднее 80) корректируется вверх."""
        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 255)  # всё — субъект
        target = [180, 200]

        result = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        assert result_arr.mean() > 80, "Тёмное лицо должно стать ярче"

    def test_bright_face_gets_darkened(self):
        """Слишком яркое лицо (среднее 240) корректируется вниз."""
        gray = Image.new("L", (200, 200), 240)
        mask = Image.new("L", (200, 200), 255)
        target = [180, 200]

        result = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        assert result_arr.mean() < 240, "Яркое лицо должно стать темнее"

    def test_correct_face_unchanged(self):
        """Лицо в целевом диапазоне не корректируется."""
        gray = Image.new("L", (200, 200), 190)
        mask = Image.new("L", (200, 200), 255)
        target = [180, 200]

        result = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        # Должно быть почти неизменным
        assert abs(result_arr.mean() - 190) < 3, \
            f"Лицо в диапазоне не должно корректироваться: {result_arr.mean():.0f}"

    def test_empty_mask_returns_original(self):
        """Пустая маска — изображение не меняется."""
        gray = Image.new("L", (200, 200), 100)
        mask = Image.new("L", (200, 200), 0)  # пустая
        target = [180, 200]

        result = check_face_brightness(gray, target, mask, glow_size=0)
        assert np.array(result).mean() == 100, "Пустая маска — без коррекции"
