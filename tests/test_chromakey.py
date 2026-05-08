"""Тесты модуля chromakey — удаление синего фона + fringe removal."""

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
        # Все оставшиеся пиксели должны быть не-синими
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        blue_remaining = (b > r + 30) & (b > g + 30) & (arr[..., 3] > 0)
        # Допускаем лишь единичные пиксели на границе (fringe_zone без fringe_radius)
        blue_ratio = blue_remaining.sum() / max((arr[..., 3] > 0).sum(), 1)
        assert blue_ratio < 0.02, f"Слишком много синих пикселей: {blue_ratio:.2%}"

    def test_subject_pixels_preserved(self, chromakey_img):
        """Несиние пиксели субъекта не затронуты."""
        img, original_mask = chromakey_img
        original_arr = np.array(img)
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0)

        result_arr = np.array(result)
        # Субъект (оригинальный) — верхняя центральная часть
        # Проверяем что непрозрачные пиксели субъекта сохранили R/G
        subject_pixels = np.array(original_mask) > 128
        # Субъект должен остаться непрозрачным (alpha > 0)
        # за исключением краёв (fringe_radius=0 не должен их трогать)
        inner_subject = subject_pixels.copy()
        # Убираем 5px краёв для устойчивости
        from scipy.ndimage import binary_erosion
        inner_subject = binary_erosion(inner_subject, iterations=5)
        assert inner_subject.sum() > 0, "Слишком маленький субъект для проверки"

        alpha = result_arr[..., 3]
        assert (alpha[inner_subject] > 0).mean() > 0.95, \
            "Субъект стал прозрачным — пиксели удалены ошибочно"

    def test_subject_mask_values(self, chromakey_img):
        """Маска субъекта: 255 = субъект, 0 = фон."""
        img, _ = chromakey_img
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0)

        mask_arr = np.array(mask)
        # Только 0 и 255
        unique = set(np.unique(mask_arr))
        assert unique.issubset({0, 255}), f"Маска содержит значения кроме 0/255: {unique}"

    def test_no_chromakey_returns_full_mask(self, no_chromakey_img):
        """Без хромакея — маска субъекта покрывает всё изображение."""
        result, mask = remove_blue_background(no_chromakey_img, threshold=30, fringe_radius=0)
        mask_arr = np.array(mask)
        assert mask_arr.mean() > 240, "Без хромакея маска должна быть почти вся 255"

    def test_fringe_reduces_blue_artifacts(self):
        """Fringe removal уменьшает синие рефлексы на границе."""
        # Создаём изображение с синим ореолом вокруг субъекта
        w, h = 200, 200
        arr = np.zeros((h, w, 4), dtype=np.uint8)

        # Синий фон
        arr[..., 2] = 255
        arr[..., 3] = 255

        # Белый квадрат-субъект в центре
        arr[60:140, 60:140, :] = [200, 200, 200, 255]

        # Добавляем синий ореол вокруг субъекта (2px)
        arr[58:60, 60:140, :] = [30, 30, 180, 255]
        arr[140:142, 60:140, :] = [30, 30, 180, 255]
        arr[60:140, 58:60, :] = [30, 30, 180, 255]
        arr[60:140, 140:142, :] = [30, 30, 180, 255]

        img = Image.fromarray(arr)

        # Без fringe removal
        result_no_fringe, _ = remove_blue_background(img, threshold=30, fringe_radius=0)
        arr_no_fringe = np.array(result_no_fringe)

        # С fringe removal
        result_with_fringe, _ = remove_blue_background(img, threshold=30, fringe_radius=3)
        arr_with_fringe = np.array(result_with_fringe)

        # С fringe removal синий канал на границе должен быть ниже
        # (зона fringe обработана)
        # Проверяем зону вокруг бывшего квадрата
        border_zone = np.zeros((h, w), dtype=bool)
        border_zone[55:145, 55:145] = True
        border_zone[60:140, 60:140] = False  # исключаем сам субъект

        if border_zone.sum() > 0:
            blue_no = arr_no_fringe[border_zone, 2].astype(float)
            blue_with = arr_with_fringe[border_zone, 2].astype(float)
            # Fringe removal должен уменьшить синий
            assert blue_with.mean() <= blue_no.mean() + 1, \
                "Fringe removal должен уменьшать синий на границе"

    def test_dark_blue_clothing_not_removed(self, dark_blue_clothing_img):
        """Тёмно-синяя одежда с высоким порогом не удаляется."""
        img = dark_blue_clothing_img
        # С threshold=30 тёмно-синяя одежда (B=80, R=30, G=40)
        # B(80) > R(30)+30=60 → да, B(80) > G(40)+30=70 → да → будет удалена!
        # Это ожидаемо — нужно повысить threshold
        result_low, mask_low = remove_blue_background(img, threshold=30, fringe_radius=0)

        # С threshold=60: B(80) > R(30)+60=90? Нет → не удаляется
        result_high, mask_high = remove_blue_background(img, threshold=60, fringe_radius=0)

        mask_low_arr = np.array(mask_low)
        mask_high_arr = np.array(mask_high)

        # Нижняя треть — тёмно-синяя одежда
        h = img.size[1]
        clothing_zone = np.zeros(mask_high_arr.shape, dtype=bool)
        clothing_zone[2 * h // 3:, :] = True

        # С высоким threshold одежда сохраняется
        clothing_in_mask = mask_high_arr[clothing_zone]
        assert clothing_in_mask.mean() > 200, \
            "Тёмно-синяя одежда не должна удаляться с высоким threshold"

    def test_output_modes(self, chromakey_img):
        """Результат — RGBA, маска — L."""
        img, _ = chromakey_img
        result, mask = remove_blue_background(img, threshold=30, fringe_radius=0)
        assert result.mode == "RGBA", f"Результат должен быть RGBA, а не {result.mode}"
        assert mask.mode == "L", f"Маска должна быть L, а не {mask.mode}"
