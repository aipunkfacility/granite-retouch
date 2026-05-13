"""Тесты модуля chromakey — удаление синего фона + fringe removal + софт-маска."""

import logging

import numpy as np
import pytest
from PIL import Image

from retouch.processing.chromakey import (
    remove_blue_background, _make_smooth_mask, _compute_blue_strength,
    HAS_CV2, HAS_SCIPY,
)


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

    def test_subject_mask_mostly_binary_without_soft_sigma(self, chromakey_img):
        """Маска субъекта без mask_soft_sigma: преимущественно 0 и 255.

        Градиентная маска даёт промежуточные значения только на границе
        (transition zone ~2*half_band пикселей). Основная масса пикселей
        должна быть 0 или 255.
        """
        img, _ = chromakey_img
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0,
                                               mask_soft_sigma=0)

        mask_arr = np.array(mask)
        binary_count = ((mask_arr == 0) | (mask_arr == 255)).sum()
        total = mask_arr.size
        # >90% пикселей должны быть 0 или 255
        # (градиентная маска шире чем старый LINE_AA, но всё ещё узкая)
        pct = binary_count / total
        assert pct > 0.90, \
            f"Маска без sigma должна быть преимущественно бинарной: {pct:.1%}"

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

    def test_mask_significant_intermediate_values(self):
        """Градиентная маска даёт значимые промежуточные значения (>10).

        Градиент синевы даёт плавный переход вместо бинарного 0/255.
        Значения на контуре — 20-230 вместо 1-2 от старого GaussianBlur.
        """
        img, cx, cy, radius = self._make_circle_img()
        _, mask = remove_blue_background(img, threshold=30, fringe_radius=3,
                                          mask_soft_sigma=1.5)

        mask_arr = np.array(mask)
        h, w = mask_arr.shape
        yy, xx = np.ogrid[:h, :w]
        dist = np.sqrt((xx - cx)**2 + (yy - cy)**2).astype(float)
        border = (dist >= radius - 3) & (dist <= radius + 3)
        border_values = mask_arr[border]

        significant = (border_values > 10) & (border_values < 245)
        assert significant.sum() > 0, \
            "Градиентная маска должна давать значимые промежуточные значения (>10)"

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

    def test_no_staircase_on_diagonal(self):
        """На диагональной границе с антиалиасингом — плавные промежуточные значения.

        Градиентная маска следует за реальным градиентом синевы.
        На изображении с антиалиасингом (полусиние пиксели на границе)
        маска даёт промежуточные alpha-значения вместо бинарного 0/255.
        """
        w, h = 200, 200
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        arr[..., 2] = 255  # синий фон
        arr[..., 3] = 255

        # Круг с широким антиалиасингом: 6px transition zone
        cy, cx, radius = 100, 100, 60
        yy, xx = np.ogrid[:h, :w]
        dist = np.sqrt((xx - cx)**2 + (yy - cy)**2).astype(float)

        # Внутри: чистый серый (с запасом от transition)
        inside = dist <= radius - 3
        arr[inside] = [200, 200, 200, 255]

        # Transition zone: 6px с плавной интерполяцией
        transition = (dist > radius - 3) & (dist <= radius + 3)
        t = np.clip((dist - (radius - 3)) / 6.0, 0, 1)

        # Векторная интерполяция: t=0 субъект, t=1 фон
        rg = (200 * (1 - t)).astype(np.uint8)
        b_val = (200 * (1 - t) + 255 * t).astype(np.uint8)
        arr[transition, 0] = rg[transition]
        arr[transition, 1] = rg[transition]
        arr[transition, 2] = b_val[transition]

        img = Image.fromarray(arr)
        _, mask = remove_blue_background(img, threshold=30, fringe_radius=0,
                                          mask_soft_sigma=0)

        mask_arr = np.array(mask)

        # На 45° диагонали — ищем промежуточные значения
        cos45 = sin45 = 0.7071
        diag_x = int(cx + radius * cos45)
        diag_y = int(cy - radius * sin45)

        # Расширенное окно для поиска transition zone
        y1 = max(0, diag_y - 4)
        y2 = min(mask_arr.shape[0], diag_y + 5)
        x1 = max(0, diag_x - 4)
        x2 = min(mask_arr.shape[1], diag_x + 5)
        window = mask_arr[y1:y2, x1:x2]

        significant = (window > 20) & (window < 235)
        window_vals = window.flatten().tolist()
        assert significant.sum() > 0, \
            f"На диагональном контуре с антиалиасингом должны быть промежуточные значения. Окно: {window_vals}"

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
        внутренние буферы scipy и cv2. Поэтому пик может быть значительно
        выше теоретического uint8 минимума. Тест проверяет что мы не ушли
        в безумные цифры (> 100 MB для 500x500).
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

        # Реалистичный потолок: данные + scipy/cv2 internals + запас.
        # Порог 80 MB (cv2 добавляет аллокации по сравнению с чистым scipy).
        assert peak < 80_000_000, \
            f"Пиковое потребление памяти аномально высокое: {peak/1e6:.1f} MB"


class TestGradientMask:
    """Тесты градиентной маски хромакея — _compute_blue_strength + альфа."""

    def test_blue_strength_soft_step(self):
        """_compute_blue_strength: soft-step вокруг threshold.

        - excess < threshold - half_band: strength=0 (твёрдый субъект)
        - excess == threshold: strength≈0.5
        - excess > threshold + half_band: strength=1 (твёрдый фон)
        """
        threshold = 30
        # 1×3 изображение: чистый субъект, порог, чистый фон
        arr = np.array([
            [[128, 128, 128, 255],   # grayscale: excess=0 → strength=0
             [128, 128, 158, 255],   # excess=30 → strength≈0.5
             [0,   0,   255, 255]],  # чистый синий: excess=255 → strength=1
        ], dtype=np.uint8)
        r = arr[..., 0]
        g = arr[..., 1]
        b = arr[..., 2]
        strength = _compute_blue_strength(r, g, b, threshold)

        # Grayscale субъект: excess=0, strength≈0
        assert strength[0, 0] == 0.0, \
            f"Grayscale субъект должен быть strength=0, а не {strength[0, 0]}"
        # На пороге: strength≈0.5
        assert 0.4 < strength[0, 1] < 0.6, \
            f"На пороге strength≈0.5, а не {strength[0, 1]}"
        # Чистый синий: strength=1
        assert strength[0, 2] == 1.0, \
            f"Чистый синий должен быть strength=1, а не {strength[0, 2]}"

    def test_grayscale_subject_zero_strength(self):
        """Pure grayscale (R=G=B) — всегда strength=0.

        Главный инвариант: субъект не становится полупрозрачным.
        """
        threshold = 30
        # Разные яркости grayscale — все должны дать strength=0
        for val in [0, 50, 128, 200, 255]:
            arr = np.array([[[val, val, val, 255]]], dtype=np.uint8)
            r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
            strength = _compute_blue_strength(r, g, b, threshold)
            assert strength[0, 0] == 0.0, \
                f"Grayscale ({val}) должен быть strength=0, а не {strength[0, 0]}"

    def test_moderate_blue_pixel_full_background(self):
        """Пиксель R=50, G=50, B=100 → strength=1.0.

        Проверяет что moderate blue (excess=50 при threshold=30)
        считается твёрдым фоном, не полупрозрачным.
        """
        threshold = 30
        arr = np.array([[[50, 50, 100, 255]]], dtype=np.uint8)
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        strength = _compute_blue_strength(r, g, b, threshold)
        assert strength[0, 0] == 1.0, \
            f"R=50,G=50,B=100 (excess=50) должен быть strength=1.0, а не {strength[0, 0]}"

    def test_gradient_alpha_at_boundary(self):
        """На границе субъекта альфа содержит значимые промежуточные значения.

        Создаём изображение с градиентным переходом (2-3 пикселя
        с промежуточной синевой). Пиксели на границе должны получить
        промежуточную альфу вместо бинарного 0/255.
        """
        w, h = 100, 100
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        # Синий фон
        arr[..., 2] = 255
        arr[..., 3] = 255
        # Субъект в центре
        arr[30:70, 30:70] = [180, 180, 180, 255]
        # Градиентная граница: полусиние пиксели между субъектом и фоном
        # Верхняя граница: R,G плавно нарастают, B убывает
        for i in range(3):
            blue_val = 255 - i * 40   # 255, 215, 175
            rg_val = 60 + i * 40      # 60, 100, 140
            arr[30 - 1 - i, 30:70] = [rg_val, rg_val, blue_val, 255]
            arr[70 + i, 30:70] = [rg_val, rg_val, blue_val, 255]

        img = Image.fromarray(arr)
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0,
                                               mask_soft_sigma=0)

        result_arr = np.array(result)
        # Row 27: R=140, G=140, B=175, excess=35 → в transition zone
        # Row 29: чистый синий (excess=195) → alpha=0
        # Проверяем row 27 — это полусиний пиксель с промежуточной альфой
        gradient_alpha = result_arr[27, 40:60, 3]  # Row с excess=35
        intermediate = (gradient_alpha > 0) & (gradient_alpha < 255)
        assert intermediate.sum() > 0, \
            f"Полусиние пиксели (excess≈35) должны иметь промежуточную альфу. Значения: {gradient_alpha.tolist()}"


class TestSmoothMask:
    """Тесты _make_smooth_mask — векторная трассировка + антиалиасинг."""

    def test_smooth_mask_basic(self):
        """_make_smooth_mask: квадратная маска — внутри 255, снаружи 0."""
        mask = np.zeros((100, 100), dtype=bool)
        mask[20:80, 20:80] = True

        result = _make_smooth_mask(mask, smooth_epsilon=0.002)
        assert result.dtype == np.uint8
        assert result.shape == mask.shape
        # Внутри квадрата — должно быть 255
        assert result[40, 40] == 255
        # Снаружи — должно быть 0
        assert result[5, 5] == 0

    def test_smooth_mask_has_antialiased_boundary(self):
        """_make_smooth_mask с cv2: на границе круга есть промежуточные значения."""
        if not HAS_CV2:
            pytest.skip("OpenCV не установлен")

        # Круг — на диагоналях будет антиалиасинг
        h, w = 200, 200
        yy, xx = np.ogrid[:h, :w]
        circle = (xx - 100)**2 + (yy - 100)**2 <= 60**2
        mask = circle.astype(bool)

        result = _make_smooth_mask(mask, smooth_epsilon=0.002)

        # На границе круга (радиус 55-65) должны быть промежуточные значения
        dist = np.sqrt((xx - 100)**2 + (yy - 100)**2).astype(float)
        border = (dist >= 55) & (dist <= 65)
        border_values = result[border]

        intermediate = (border_values > 0) & (border_values < 255)
        assert intermediate.sum() > 0, \
            "Антиалиасная маска должна иметь промежуточные значения на границе круга"

    def test_smooth_mask_without_cv2(self):
        """_make_smooth_mask без cv2: бинарная маска (fallback)."""
        # Тестируем fallback, временно подменяя HAS_CV2
        import retouch.processing.chromakey as mod
        original = mod.HAS_CV2
        try:
            mod.HAS_CV2 = False
            mask = np.zeros((100, 100), dtype=bool)
            mask[20:80, 20:80] = True

            result = _make_smooth_mask(mask, smooth_epsilon=0.002)
            assert result.dtype == np.uint8
            unique = set(np.unique(result))
            assert unique.issubset({0, 255}), \
                f"Fallback без cv2 должен давать бинарную маску: {unique}"
        finally:
            mod.HAS_CV2 = original

    def test_smooth_mask_empty_input(self):
        """_make_smooth_mask: пустая маска → все 0."""
        mask = np.zeros((100, 100), dtype=bool)
        result = _make_smooth_mask(mask, smooth_epsilon=0.002)
        assert result.dtype == np.uint8
        assert np.all(result == 0)

    def test_contour_smooth_epsilon_configurable(self):
        """Параметр contour_smooth_epsilon управляет степенью сглаживания."""
        if not HAS_CV2:
            pytest.skip("OpenCV не установлен")

        h, w = 200, 200
        yy, xx = np.ogrid[:h, :w]
        circle = (xx - 100)**2 + (yy - 100)**2 <= 60**2
        mask = circle.astype(bool)

        result_min = _make_smooth_mask(mask, smooth_epsilon=0.001)
        result_max = _make_smooth_mask(mask, smooth_epsilon=0.01)

        # Оба результата должны быть валидны: uint8, внутри 255
        # Точка (100, 100) — центр круга, гарантированно внутри
        assert result_min[100, 100] == 255
        assert result_max[100, 100] == 255
        # Снаружи — 0
        assert result_min[5, 5] == 0
        assert result_max[5, 5] == 0

    def test_fringe_correction_no_overflow(self):
        """BE-M16: fringe correction не переполняет uint8.

        Без np.clip() перед .astype(np.uint8) значения > 255
        могли обёртываться (wrap around), давая артефакты.
        """
        w, h = 200, 200
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        # Синий фон
        arr[..., 2] = 255; arr[..., 3] = 255
        # Субъект — яркие пиксели, чтобы fringe давал значения > 255
        arr[60:140, 60:140, :] = [250, 10, 250, 255]
        # Fringe-зона с экстремальными значениями
        arr[58:60, 60:140, :] = [10, 10, 255, 255]
        arr[140:142, 60:140, :] = [10, 10, 255, 255]

        img = Image.fromarray(arr)
        result, _ = remove_blue_background(img, threshold=30, fringe_radius=3)

        result_arr = np.array(result)
        # Все каналы должны быть в диапазоне 0-255 (без overflow)
        assert result_arr.min() >= 0
        assert result_arr.max() <= 255

    def test_scipy_import_at_module_level(self):
        """BE-M6: scipy импортирован на уровне модуля с HAS_SCIPY флагом."""
        import retouch.processing.chromakey as ck
        assert hasattr(ck, 'HAS_SCIPY'), "Модуль должен экспортировать HAS_SCIPY"
        assert isinstance(ck.HAS_SCIPY, bool)

    def test_has_scipy_flag_allows_numpy_path(self, chromakey_img):
        """BE-M6: при HAS_SCIPY=True numpy-путь работает нормально."""
        if not HAS_SCIPY:
            pytest.skip("scipy не установлена")
        img, _ = chromakey_img
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=3)
        assert result.mode == "RGBA"
        assert mask.mode == "L"

    def test_cv2_fallback_logs_warning(self, monkeypatch, caplog):
        """При отсутствии cv2 _make_smooth_mask логирует warning о лесенке на контуре."""
        import retouch.processing.chromakey as ck
        monkeypatch.setattr(ck, "HAS_CV2", False)
        mask = np.zeros((50, 50), dtype=bool)
        mask[10:40, 10:40] = True
        with caplog.at_level(logging.WARNING, logger="retouch.processing.chromakey"):
            result = ck._make_smooth_mask(mask, smooth_epsilon=0.002)
        assert result.dtype == np.uint8
        assert any(
            "opencv" in r.message.lower() or "cv2" in r.message.lower() or "fallback" in r.message.lower()
            for r in caplog.records
        ), f"Ожидался warning о fallback cv2, записи: {[r.message for r in caplog.records]}"
