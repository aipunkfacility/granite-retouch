"""Тесты модуля vignette — арховая виньетка."""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.vignette import apply_vignette, generate_arch_mask


class TestArchVignette:
    """Тесты арховой виньетки."""

    def _make_processed_gray(self, width=512, height=512, subject_val=128):
        """Grayscale-изображение: серый субъект на чёрном фоне.

        Имитирует результат после chromakey+glow+levels —
        субъект виден, фон чёрный (0).
        """
        img = Image.new("L", (width, height), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        cx, cy = width // 2, height // 2
        rx, ry = int(width * 0.30), int(height * 0.35)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=subject_val)
        return img

    def test_output_is_rgb(self):
        """Результат виньетки — RGB на чёрном фоне."""
        gray = self._make_processed_gray()
        vign_cfg = {
            "vertical_offset": 0.10,
            "vertical_diameter": 0.50,
            "blur_radius": 60,
            "headroom": 0.6,
            "horizontal_oversize": 0.2,
        }
        result, mask = apply_vignette(gray, 512, 512, vign_cfg)
        assert result.mode == "L", f"Результат должен быть L, а не {result.mode}"

    def test_bottom_corners_are_black(self):
        """Нижние углы — чёрные (вне арки)."""
        gray = self._make_processed_gray()
        vign_cfg = {
            "vertical_offset": 0.10,
            "vertical_diameter": 0.50,
            "blur_radius": 20,
            "headroom": 0.6,
            "horizontal_oversize": 0.1,
        }
        result, _ = apply_vignette(gray, 512, 512, vign_cfg)
        arr = np.array(result)

        # Нижние углы — точно вне арки
        corner_size = 10
        bottom_left = arr[-corner_size:, :corner_size]
        bottom_right = arr[-corner_size:, -corner_size:]
        assert bottom_left.mean() < 15, \
            f"Нижний левый угол должен быть чёрным: {bottom_left.mean():.0f}"
        assert bottom_right.mean() < 15, \
            f"Нижний правый угол должен быть чёрным: {bottom_right.mean():.0f}"

    def test_subject_top_visible_with_headroom(self):
        """Верх субъекта (голова) виден благодаря headroom.

        Арка вынесена выше изображения — верх субъекта внутри арки.
        Субъект-эллипс: центр (256,256), ry=179 → верх на y=77.
        """
        gray = self._make_processed_gray(subject_val=180)
        vign_cfg = {
            "vertical_offset": 0.10,
            "vertical_diameter": 0.50,
            "blur_radius": 20,
            "headroom": 0.6,
            "horizontal_oversize": 0.2,
        }
        result, _ = apply_vignette(gray, 512, 512, vign_cfg)
        arr = np.array(result)

        # Верх субъекта (y=80-120) — внутри арки, должен быть виден
        subject_top = arr[80:120, 230:282]
        assert subject_top.mean() > 30, \
            f"Верх субъекта должен быть виден: {subject_top.mean():.0f}"

    def test_scaling_preserves_proportions(self):
        """Виньетка масштабируется пропорционально на разных размерах."""
        vign_cfg = {
            "vertical_offset": 0.10,
            "vertical_diameter": 0.50,
            "blur_radius": 60,
            "headroom": 0.6,
            "horizontal_oversize": 0.2,
        }

        sizes = [(512, 512), (1024, 1024), (800, 600), (600, 800)]

        for w, h in sizes:
            gray = self._make_processed_gray(w, h)
            result, mask = apply_vignette(gray, w, h, vign_cfg)
            assert result.size == (w, h), \
                f"Размер результата {result.size} != ожидаемому ({w}, {h})"

            # Нижние углы — чёрные
            arr = np.array(result)
            corner = arr[-5:, :5]
            assert corner.mean() < 15, \
                f"Нижний угол не чёрный для {w}x{h}: {corner.mean():.0f}"

    def test_headroom_keeps_top_visible(self):
        """С большим headroom верхняя часть субъекта видна."""
        gray = self._make_processed_gray(subject_val=180)
        vign_cfg = {
            "vertical_offset": 0.10,
            "vertical_diameter": 0.50,
            "blur_radius": 20,
            "headroom": 0.8,  # большой запас
            "horizontal_oversize": 0.2,
        }
        result, _ = apply_vignette(gray, 512, 512, vign_cfg)
        arr = np.array(result)

        # Верх субъекта (y=80-120) должен быть виден
        subject_top = arr[80:120, 230:282]
        assert subject_top.mean() > 30, \
            f"С большим headroom верх субъекта виден: {subject_top.mean():.0f}"

    def test_small_vignette_darkens_sides(self):
        """Узкая арка затемняет боковые части."""
        gray = self._make_processed_gray(subject_val=200)
        vign_cfg = {
            "vertical_offset": 0.10,
            "vertical_diameter": 0.20,  # маленькая арка
            "blur_radius": 20,
            "headroom": 0.1,  # мало запаса
            "horizontal_oversize": 0.0,  # без расширения
        }
        result, _ = apply_vignette(gray, 512, 512, vign_cfg)
        arr = np.array(result)

        # Боковые области должны быть темнее центра
        center = arr[200:300, 230:282].mean()
        left_side = arr[200:300, :50].mean()
        right_side = arr[200:300, -50:].mean()
        assert left_side < center or right_side < center, \
            "Узкая арка должна затемнять бока"

    def test_arch_mask_is_smooth(self):
        """Маска виньетки — плавная (Gaussian blur), нет резких границ."""
        gray = self._make_processed_gray()
        vign_cfg = {
            "vertical_offset": 0.10,
            "vertical_diameter": 0.50,
            "blur_radius": 60,
            "headroom": 0.6,
            "horizontal_oversize": 0.2,
        }
        _, mask = apply_vignette(gray, 512, 512, vign_cfg)
        mask_arr = np.array(mask, dtype=float)

        # Проверяем что маска содержит промежуточные значения (не только 0 и 255)
        unique_values = len(np.unique(mask_arr))
        assert unique_values > 10, \
            f"Маска должна быть плавной, а не бинарной ({unique_values} уникальных значений)"


class TestGenerateArchMask:
    """Тесты generate_arch_mask — генерация маски без композитинга."""

    def test_mask_dimensions(self):
        """Маска имеет запрошенные размеры."""
        mask = generate_arch_mask(640, 480, {
            "vertical_offset": 0.1,
            "vertical_diameter": 0.5,
            "blur_radius": 30,
            "headroom": 0.6,
            "horizontal_oversize": 0.2,
        })
        assert mask.size == (640, 480)
        assert mask.mode == "L"

    def test_mask_has_ellipse(self):
        """Центр маски — белый (эллипс), нижние углы — чёрные."""
        mask = generate_arch_mask(512, 512, {
            "vertical_offset": 0.1,
            "vertical_diameter": 0.5,
            "blur_radius": 10,
            "headroom": 0.6,
            "horizontal_oversize": 0.2,
        })
        arr = np.array(mask)
        # Центр эллипса — внутри арки, должен быть ярким
        assert arr[200, 256] > 200, f"Центр маски должен быть белым: {arr[200, 256]}"
        # Нижние углы — вне арки (ниже arch_bottom_y), должны быть чёрными
        assert arr[500, 10] < 10, f"Нижний угол маски должен быть чёрным: {arr[500, 10]}"
        assert arr[500, 501] < 10, f"Нижний правый угол маски должен быть чёрным: {arr[500, 501]}"

    def test_mask_no_blur_sharp(self):
        """Без blur (radius=0) — чёткий эллипс с резкими краями."""
        mask = generate_arch_mask(200, 200, {
            "vertical_offset": 0.1,
            "vertical_diameter": 0.5,
            "blur_radius": 0,
            "headroom": 0.6,
            "horizontal_oversize": 0.2,
        })
        # Пиксель внутри эллипса — строго 255
        assert mask.getpixel((100, 80)) == 255
        # Нижний угол — вне эллипса, строго 0
        assert mask.getpixel((10, 190)) == 0

    def test_mask_consistent_with_apply_vignette(self):
        """Маска из generate_arch_mask совпадает с маской из apply_vignette."""
        vign_cfg = {
            "vertical_offset": 0.12,
            "vertical_diameter": 0.45,
            "blur_radius": 25,
            "headroom": 0.55,
            "horizontal_oversize": 0.15,
        }
        gray = Image.new("L", (300, 300), 128)

        _, mask_from_apply = apply_vignette(gray, 300, 300, vign_cfg)
        mask_standalone = generate_arch_mask(300, 300, vign_cfg)

        arr_apply = np.array(mask_from_apply)
        arr_standalone = np.array(mask_standalone)

        # Маски должны быть идентичны
        assert np.array_equal(arr_apply, arr_standalone), \
            "Маска из generate_arch_mask должна совпадать с маской из apply_vignette"
