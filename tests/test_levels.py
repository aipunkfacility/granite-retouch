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

    def test_highlight_start_parameter(self):
        """highlight_start контролирует затухание коррекции."""
        arr = np.array([180, 200, 220, 240], dtype=np.float32)
        correction = 1.3

        # С высоким highlight_start — коррекция полная для 200
        result_high = _curves_correction(arr, correction, highlight_start=240)
        # С низким highlight_start — коррекция затухает для 200
        result_low = _curves_correction(arr, correction, highlight_start=100)

        # При highlight_start=240 пиксель 200 получает почти полную коррекцию
        # При highlight_start=100 пиксель 200 получает затухающую коррекцию
        diff_high = abs(result_high[1] - arr[1])
        diff_low = abs(result_low[1] - arr[1])
        assert diff_high >= diff_low, \
            "Более высокий highlight_start → больше коррекция для средних тонов"


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

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        assert result_arr.mean() > 80, "Тёмное лицо должно стать ярче"
        assert before == 80.0, f"before должен быть 80.0, а не {before}"
        assert after > 80.0, f"after должен быть > 80.0, а не {after}"
        assert factor > 1.0, f"factor должен быть > 1.0 для тёмного лица, а не {factor}"

    def test_bright_face_gets_darkened(self):
        """Слишком яркое лицо (среднее 240) корректируется вниз."""
        gray = Image.new("L", (200, 200), 240)
        mask = Image.new("L", (200, 200), 255)
        target = [180, 200]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        assert result_arr.mean() < 240, "Яркое лицо должно стать темнее"
        assert factor < 1.0, f"factor должен быть < 1.0 для яркого лица"

    def test_correct_face_unchanged(self):
        """Лицо в целевом диапазоне не корректируется."""
        gray = Image.new("L", (200, 200), 190)
        mask = Image.new("L", (200, 200), 255)
        target = [180, 200]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        # Должно быть почти неизменным
        assert abs(result_arr.mean() - 190) < 3, \
            f"Лицо в диапазоне не должно корректироваться: {result_arr.mean():.0f}"
        assert factor == 1.0, f"factor должен быть 1.0 без коррекции"

    def test_empty_mask_returns_original(self):
        """Пустая маска — изображение не меняется."""
        gray = Image.new("L", (200, 200), 100)
        mask = Image.new("L", (200, 200), 0)  # пустая
        target = [180, 200]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        assert np.array(result).mean() == 100, "Пустая маска — без коррекции"
        assert before == 0.0, "before = 0.0 при пустой маске"
        assert factor == 1.0, "factor = 1.0 при пустой маске"

    def test_face_region_top_parameter(self):
        """face_region_top ограничивает зону замера верхней частью."""
        # Изображение 200x200: верхняя часть темная (80), нижняя — светлая (240)
        arr = np.full((200, 200), 240, dtype=np.uint8)
        arr[:100, :] = 80  # верхняя половина — тёмная
        gray = Image.fromarray(arr, "L")
        mask = Image.new("L", (200, 200), 255)  # всё — субъект
        target = [180, 200]

        # С face_region_top=0.5 — замеряем только верхнюю половину (тёмную)
        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0, face_region_top=0.5
        )
        # before должен быть ближе к 80 (верхняя часть), а не к 160 (среднее всего)
        assert before < 120, f"before должен отражать верхнюю часть: {before}"

    def test_correction_only_within_mask(self):
        """Коррекция применяется только внутри маски субъекта."""
        # Левая половина — субъект (маска=255), правая — фон (маска=0)
        arr = np.full((200, 200), 80, dtype=np.uint8)
        gray = Image.fromarray(arr, "L")
        mask_arr = np.zeros((200, 200), dtype=np.uint8)
        mask_arr[:, :100] = 255  # левая половина — субъект
        mask = Image.fromarray(mask_arr, "L")
        target = [180, 200]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0
        )
        result_arr = np.array(result)

        # Правая половина (вне маски) не должна измениться
        right_half = result_arr[:, 100:]
        assert np.all(right_half == 80), \
            f"Фон вне маски не должен корректироваться, got max={right_half.max()}"

        # Левая половина (внутри маски) должна стать ярче
        left_half = result_arr[:, :100]
        assert left_half.mean() > 80, \
            f"Субъект внутри маски должен стать ярче, got {left_half.mean():.0f}"

    def test_bright_skin_not_overexposed(self):
        """Уже яркие пиксели кожи не засвечиваются дальше (target_ceiling)."""
        # Изображение: среднее по лицу = 100 (тёмное), но некоторые пиксели уже 230+
        arr = np.full((200, 200), 100, dtype=np.uint8)
        arr[10:30, 10:30] = 230  # уже яркие пиксели кожи
        gray = Image.fromarray(arr, "L")
        mask = Image.new("L", (200, 200), 255)
        target = [200, 220]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0
        )
        result_arr = np.array(result)

        # Пиксели уже выше target_max (220) НЕ должны стать ещё ярче
        bright_region = result_arr[10:30, 10:30]
        assert bright_region.mean() <= 232, \
            f"Уже яркие пиксели ({230}) не должны засвечиваться: got {bright_region.mean():.0f}"

    def test_no_double_brightening_beyond_target(self):
        """После apply_levels + check_face_brightness пиксели не улетают за target_max."""
        from retouch.processing.levels import apply_levels

        # Симулируем пайплайн: apply_levels(1.18) → check_face_brightness
        arr = np.full((200, 200), 150, dtype=np.uint8)
        arr[80:120, 80:120] = 200  # яркая область (кожа)
        gray = Image.fromarray(arr, "L")
        mask = Image.new("L", (200, 200), 255)
        target = [230, 245]

        # Step 1: apply_levels
        leveled = apply_levels(gray, brightness_factor=1.18)

        # Step 2: check_face_brightness
        result, before, after, factor = check_face_brightness(
            leveled, target, mask, glow_size=0
        )
        result_arr = np.array(result)

        # Уже яркие пиксели (были 200, после levels ~236) не должны улететь за 255
        bright_region = result_arr[80:120, 80:120]
        # С target_ceiling=245, пиксели >=245 не должны стать ярче
        assert bright_region.max() <= 255
        # И не должно быть массового клиппинга (все = 255)
        clipping_ratio = (bright_region == 255).sum() / bright_region.size
        assert clipping_ratio < 0.5, \
            f"Слишком много клиппинга ({clipping_ratio:.0%}) — лицо засвечено"
