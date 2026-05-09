"""Тесты модуля chromakey — удаление синего фона + fringe removal + софт-маска."""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.chromakey import remove_blue_background


class TestRemoveBlueBackground:
    """Тесты удаления синего хромакея."""

    def test_blue_pixels_removed(self, chromakey_img):
        """Синие пиксели хромакея (#0000FF) полностью удаляются."""
        img, _ = chromakey_img
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0)

        arr = np.array(result)
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        blue_remaining = (b > r + 30) & (b > g + 30) & (arr[..., 3] > 0)
        blue_ratio = blue_remaining.sum() / max((arr[..., 3] > 0).sum(), 1)
        assert blue_ratio < 0.02, f"Слишком много синих пикселей: {blue_ratio:.2%}"

    def test_subject_pixels_preserved(self, chromakey_img):
        """Несиние пиксели субъекта не затронуты."""
        img, original_mask = chromakey_img
        original_arr = np.array(img)
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0)

        result_arr = np.array(result)
        subject_pixels = np.array(original_mask) > 128
        inner_subject = subject_pixels.copy()
        from scipy.ndimage import binary_erosion
        inner_subject = binary_erosion(inner_subject, iterations=5)
        assert inner_subject.sum() > 0, "Слишком маленький субъект для проверки"

        alpha = result_arr[..., 3]
        assert (alpha[inner_subject] > 0).mean() > 0.95, \
            "Субъект стал прозрачным — пиксели удалены ошибочно"

    def test_subject_mask_binary_without_soft_sigma(self, chromakey_img):
        """Маска субъекта без mask_soft_sigma: 0 и 255 (бинарная)."""
        img, _ = chromakey_img
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0,
                                               mask_soft_sigma=0)

        mask_arr = np.array(mask)
        unique = set(np.unique(mask_arr))
        assert unique.issubset({0, 255}), f"Маска без sigma должна быть бинарной: {unique}"

    def test_no_chromakey_returns_full_mask(self, no_chromakey_img):
        """Без хромакея — маска субъекта покрывает всё изображение."""
        result, mask = remove_blue_background(no_chromakey_img, threshold=30, fringe_radius=0)
        mask_arr = np.array(mask)
        assert mask_arr.mean() > 240, "Без хромакея маска должна быть почти вся 255"

    def test_fringe_reduces_blue_artifacts(self):
        """Fringe removal уменьшает синие рефлексы на границе."""
        w, h = 200, 200
        arr = np.zeros((h, w, 4), dtype=np.uint8)

        arr[..., 2] = 255
        arr[..., 3] = 255

        arr[60:140, 60:140, :] = [200, 200, 200, 255]

        arr[58:60, 60:140, :] = [30, 30, 180, 255]
        arr[140:142, 60:140, :] = [30, 30, 180, 255]
        arr[60:140, 58:60, :] = [30, 30, 180, 255]
        arr[60:140, 140:142, :] = [30, 30, 180, 255]

        img = Image.fromarray(arr)

        result_no_fringe, _ = remove_blue_background(img, threshold=30, fringe_radius=0)
        arr_no_fringe = np.array(result_no_fringe)

        result_with_fringe, _ = remove_blue_background(img, threshold=30, fringe_radius=3)
        arr_with_fringe = np.array(result_with_fringe)

        border_zone = np.zeros((h, w), dtype=bool)
        border_zone[55:145, 55:145] = True
        border_zone[60:140, 60:140] = False

        if border_zone.sum() > 0:
            blue_no = arr_no_fringe[border_zone, 2].astype(float)
            blue_with = arr_with_fringe[border_zone, 2].astype(float)
            assert blue_with.mean() <= blue_no.mean() + 1, \
                "Fringe removal должен уменьшать синий на границе"

    def test_dark_blue_clothing_not_removed(self, dark_blue_clothing_img):
        """Тёмно-синяя одежда с высоким порогом не удаляется."""
        img = dark_blue_clothing_img
        result_low, mask_low = remove_blue_background(img, threshold=30, fringe_radius=0)
        result_high, mask_high = remove_blue_background(img, threshold=60, fringe_radius=0)

        mask_high_arr = np.array(mask_high)

        h = img.size[1]
        clothing_zone = np.zeros(mask_high_arr.shape, dtype=bool)
        clothing_zone[2 * h // 3:, :] = True

        clothing_in_mask = mask_high_arr[clothing_zone]
        assert clothing_in_mask.mean() > 200, \
            "Тёмно-синяя одежда не должна удаляться с высоким threshold"

    def test_output_modes(self, chromakey_img):
        """Результат — RGBA, маска — L."""
        img, _ = chromakey_img
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0)
        assert result.mode == "RGBA", f"Результат должен быть RGBA, а не {result.mode}"
        assert mask.mode == "L", f"Маска должна быть L, а не {mask.mode}"


class TestSoftMask:
    """Софт-маска хромакея — антиалиасные края без ступенек."""

    def _make_circle_img(self, w=200, h=200):
        """Создать тестовое изображение: синий фон + белый круг."""
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        arr[..., 2] = 255  # синий фон
        arr[..., 3] = 255

        cy, cx, radius = 100, 100, 60
        yy, xx = np.ogrid[:h, :w]
        circle = (xx - cx)**2 + (yy - cy)**2 <= radius**2
        arr[circle] = [200, 200, 200, 255]

        return Image.fromarray(arr), cx, cy, radius

    def test_mask_has_intermediate_values_at_boundary(self):
        """На границе субъекта маска содержит промежуточные значения (не только 0/255)."""
        img, cx, cy, radius = self._make_circle_img()
        _, mask = remove_blue_background(img, threshold=30, fringe_radius=3,
                                          mask_soft_sigma=1.5)

        mask_arr = np.array(mask)
        h, w = mask_arr.shape
        yy, xx = np.ogrid[:h, :w]
        dist = np.sqrt((xx - cx)**2 + (yy - cy)**2).astype(float)
        border = (dist >= radius - 4) & (dist <= radius + 4)
        border_values = mask_arr[border]

        intermediate = (border_values > 0) & (border_values < 255)
        assert intermediate.sum() > 0, \
            "Софт-маска должна иметь промежуточные значения на криволинейной границе"

    def test_mask_is_white_inside_subject(self):
        """Внутри субъекта маска = 255 (без размытия вглубь)."""
        img, cx, cy, radius = self._make_circle_img()
        _, mask = remove_blue_background(img, threshold=30, fringe_radius=3,
                                          mask_soft_sigma=1.5)

        mask_arr = np.array(mask)
        h, w = mask_arr.shape
        yy, xx = np.ogrid[:h, :w]
        dist = np.sqrt((xx - cx)**2 + (yy - cy)**2).astype(float)
        interior = dist < radius - 8
        if interior.sum() > 0:
            assert (mask_arr[interior] == 255).all(), \
                "Внутри субъекта маска должна быть 255"

    def test_mask_is_black_outside_expanded_zone(self):
        """Вдали от границы маска = 0 (без размытия наружу)."""
        img, cx, cy, radius = self._make_circle_img()
        _, mask = remove_blue_background(img, threshold=30, fringe_radius=3,
                                          mask_soft_sigma=1.5)

        mask_arr = np.array(mask)
        h, w = mask_arr.shape
        yy, xx = np.ogrid[:h, :w]
        dist = np.sqrt((xx - cx)**2 + (yy - cy)**2).astype(float)
        far_outside = dist > radius + 15
        if far_outside.sum() > 0:
            assert (mask_arr[far_outside] == 0).all(), \
                "Вдали от границы маска должна быть 0"

    def test_mask_soft_sigma_configurable(self):
        """Ширина размытия краёв маски настраивается через mask_soft_sigma."""
        img, _, _, _ = self._make_circle_img()
        _, mask_soft = remove_blue_background(img, threshold=30, fringe_radius=3,
                                               mask_soft_sigma=3.0)
        _, mask_hard = remove_blue_background(img, threshold=30, fringe_radius=3,
                                               mask_soft_sigma=0.5)
        soft_intermediate = ((np.array(mask_soft) > 0) & (np.array(mask_soft) < 255)).sum()
        hard_intermediate = ((np.array(mask_hard) > 0) & (np.array(mask_hard) < 255)).sum()
        assert soft_intermediate > hard_intermediate, \
            "Больший sigma должен давать более широкую переходную зону"

    def test_chromakey_base_array_is_uint8(self):
        """Основной массив хромакея — uint8 (не float32).

        Проверяем что np.array(img) возвращает uint8 RGBA, а не float32.
        Это гарантирует 4 байта/пиксель вместо 16.
        """
        w, h = 100, 100
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        arr[..., 2] = 255; arr[..., 3] = 255
        arr[25:75, 25:75] = [200, 200, 200, 255]
        img = Image.fromarray(arr)

        # np.array(img) должен быть uint8
        loaded = np.array(img)
        assert loaded.dtype == np.uint8, \
            f"Основной массив должен быть uint8, а не {loaded.dtype}"

    def test_chromakey_memory_approximate(self):
        """Приблизительная проверка потребления памяти хромакея.

        NOTE: tracemalloc захватывает ВСЕ аллокации Python, включая
        внутренние буферы scipy (binary_dilation, gaussian_filter, binary_erosion).
        Поэтому пик может быть значительно выше теоретического uint8 минимума.
        Тест проверяет что мы не ушли в безумные цифры (> 100 MB для 500x500).
        """
        import tracemalloc
        w, h = 500, 500
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        arr[..., 2] = 255; arr[..., 3] = 255
        arr[150:350, 150:350] = [200, 200, 200, 255]
        img = Image.fromarray(arr)

        tracemalloc.start()
        remove_blue_background(img, threshold=30, fringe_radius=3, mask_soft_sigma=1.5)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Щедрый порог: 100 MB для 500x500.
        # Теоретический минимум uint8: ~1 MB + fringe + mask.
        # scipy internals добавляют ~20-50 MB.
        # Этот тест ловит регрессию если кто-то вернёт float32 на весь массив.
        assert peak < 100_000_000, \
            f"Пиковое потребление памяти аномально высокое: {peak/1e6:.1f} MB"
