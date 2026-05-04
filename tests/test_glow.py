"""Тесты модуля glow — Inner Glow (контурный свет)."""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.glow import apply_inner_glow


class TestInnerGlow:
    """Тесты Inner Glow для лазерной и ударной гравировки."""

    def _make_gray_with_mask(self, width=512, height=512, subject_val=128):
        """Создать grayscale-изображение с маской субъекта."""
        gray = Image.new("L", (width, height), 0)
        mask = Image.new("L", (width, height), 0)

        # Эллипс-субъект в центре
        from PIL import ImageDraw
        draw_g = ImageDraw.Draw(gray)
        draw_m = ImageDraw.Draw(mask)

        cx, cy = width // 2, height // 2
        rx, ry = int(width * 0.30), int(height * 0.35)
        draw_g.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=subject_val)
        draw_m.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)

        return gray, mask

    def test_laser_glow_size_range(self):
        """Laser glow: размер 40–80px при фиксированном override."""
        gray, mask = self._make_gray_with_mask()
        laser_cfg = {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
        }

        # С override проверяем точные значения
        result, glow_size, glow_opacity = apply_inner_glow(
            gray, mask, laser_cfg, glow_size_override=60, glow_opacity_override=35
        )
        assert glow_size == 60
        assert abs(glow_opacity - 0.35) < 0.01

    def test_impact_glow_size_range(self):
        """Impact glow: размер 10–25px при фиксированном override."""
        gray, mask = self._make_gray_with_mask()
        impact_cfg = {
            "glow_size_min": 10, "glow_size_max": 25,
            "glow_opacity_min": 60, "glow_opacity_max": 80,
        }

        result, glow_size, glow_opacity = apply_inner_glow(
            gray, mask, impact_cfg, glow_size_override=15, glow_opacity_override=70
        )
        assert glow_size == 15
        assert abs(glow_opacity - 0.70) < 0.01

    def test_glow_brightens_edges(self):
        """Glow делает край субъекта светлее (контурное свечение)."""
        gray, mask = self._make_gray_with_mask(subject_val=80)
        laser_cfg = {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
        }

        result, _, _ = apply_inner_glow(
            gray, mask, laser_cfg, glow_size_override=50, glow_opacity_override=35
        )

        # Край маски субъекта должен быть светлее исходного (80)
        result_arr = np.array(result)
        mask_arr = np.array(mask)

        # Зона вблизи края: пиксели маски субъекта рядом с фоном
        from scipy.ndimage import binary_erosion
        inner = binary_erosion(mask_arr > 128, iterations=20)
        edge_zone = (mask_arr > 128) & ~inner

        if edge_zone.sum() > 0:
            edge_brightness = result_arr[edge_zone].mean()
            assert edge_brightness > 80, \
                f"Контур должен быть светлее исходного (80), а не {edge_brightness:.0f}"

    def test_low_opacity_glow_minimal_change(self):
        """Минимальный glow (opacity=1) почти не меняет изображение."""
        gray, mask = self._make_gray_with_mask(subject_val=100)
        laser_cfg = {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
        }

        result, _, _ = apply_inner_glow(
            gray, mask, laser_cfg, glow_size_override=50, glow_opacity_override=1
        )

        # С opacity=1% — изменение должно быть минимальным
        result_arr = np.array(result)
        original_arr = np.array(gray)
        diff = np.abs(result_arr.astype(float) - original_arr.astype(float))
        # Glow на 1% может дать до ~3 единиц разницы на краях
        assert diff.mean() < 5, f"Среднее изменение с opacity=1% слишком большое: {diff.mean():.1f}"

    def test_random_glow_within_range(self):
        """Случайный glow попадает в заданный диапазон (100 итераций)."""
        gray, mask = self._make_gray_with_mask()
        impact_cfg = {
            "glow_size_min": 10, "glow_size_max": 25,
            "glow_opacity_min": 60, "glow_opacity_max": 80,
        }

        sizes = []
        opacities = []
        for _ in range(100):
            _, gs, go = apply_inner_glow(gray, mask, impact_cfg)
            sizes.append(gs)
            opacities.append(go)

        assert min(sizes) >= 10 and max(sizes) <= 25, \
            f"Glow size вне диапазона: {min(sizes)}–{max(sizes)}"
        assert min(opacities) >= 0.60 and max(opacities) <= 0.80, \
            f"Glow opacity вне диапазона: {min(opacities):.2f}–{max(opacities):.2f}"

    def test_output_is_grayscale(self):
        """Результат — L (grayscale)."""
        gray, mask = self._make_gray_with_mask()
        laser_cfg = {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
        }
        result, _, _ = apply_inner_glow(
            gray, mask, laser_cfg, glow_size_override=50, glow_opacity_override=35
        )
        assert result.mode == "L", f"Результат должен быть L, а не {result.mode}"
