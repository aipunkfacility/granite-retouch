"""Тесты модуля glow — Inner Glow (контурный свет)."""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.glow import apply_inner_glow, _calculate_glow_params


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
        """Outer glow делает зону снаружи контура светлее (контурное свечение наружу)."""
        gray, mask = self._make_gray_with_mask(subject_val=80)
        laser_cfg = {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
        }

        result, _, _ = apply_inner_glow(
            gray, mask, laser_cfg, glow_size_override=50, glow_opacity_override=35
        )

        # Outer glow: зона ВНЕ маски субъекта рядом с контуром должна быть светлее 0
        result_arr = np.array(result)
        mask_arr = np.array(mask)

        # Зона снаружи маски: пиксели фона рядом с границей субъекта
        from scipy.ndimage import binary_dilation
        dilated = binary_dilation(mask_arr > 128, iterations=20)
        outer_edge = dilated & ~(mask_arr > 128)

        if outer_edge.sum() > 0:
            edge_brightness = result_arr[outer_edge].mean()
            assert edge_brightness > 0, \
                f"Outer glow должен осветлить зону снаружи контура, а средняя яркость {edge_brightness:.0f}"

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

    def test_deterministic_glow_midpoint(self):
        """D.1: Детерминированный glow — midpoint диапазона при отсутствии override."""
        gray, mask = self._make_gray_with_mask()
        impact_cfg = {
            "glow_size_min": 10, "glow_size_max": 25,
            "glow_opacity_min": 60, "glow_opacity_max": 80,
        }

        # Без override — всегда midpoint
        _, gs, go = apply_inner_glow(gray, mask, impact_cfg)
        expected_size = (10 + 25) // 2  # 17
        expected_opacity = (60 + 80) // 2 / 100  # 0.70

        assert gs == expected_size, \
            f"Glow size должен быть midpoint ({expected_size}), а не {gs}"
        assert abs(go - expected_opacity) < 0.01, \
            f"Glow opacity должен быть midpoint ({expected_opacity}), а не {go}"

        # Повторный вызов — тот же результат (детерминированность)
        _, gs2, go2 = apply_inner_glow(gray, mask, impact_cfg)
        assert gs2 == gs, "Glow size должен быть детерминированным"
        assert go2 == go, "Glow opacity должен быть детерминированным"

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


class TestAdaptiveGlow:
    """P3: адаптивные параметры glow на основе аналитики."""

    def test_laser_80w_fixed_params(self):
        """Laser 80W: фиксированные параметры (20, 15)."""
        analytics = {'subject_separation': 150, 'tonal_range': 100}
        size, opacity = _calculate_glow_params(analytics, 'laser_80w')
        assert size == 20
        assert opacity == 15

    def test_impact_low_separation_stronger_glow(self):
        """Impact: низкая сепарация → больший glow для разделения (детерминированно)."""
        analytics_low = {'subject_separation': 20, 'tonal_range': 100}
        analytics_high = {'subject_separation': 120, 'tonal_range': 100}
        size_low, opacity_low = _calculate_glow_params(analytics_low, 'impact')
        size_high, opacity_high = _calculate_glow_params(analytics_high, 'impact')
        # Низкая сепарация → нужен больший glow для разделения
        assert size_low >= size_high
        assert opacity_low >= opacity_high
        # D.1: Детерминированные значения (midpoint диапазонов)
        assert size_low == 25 and opacity_low == 77, \
            f"Expected (25, 77), got ({size_low}, {opacity_low})"
        assert size_high == 14 and opacity_high == 65, \
            f"Expected (14, 65), got ({size_high}, {opacity_high})"

    def test_laser_standard_wide_tonal_range_smaller_glow(self):
        """Laser Standard: широкий тональный диапазон → меньший glow."""
        analytics_wide = {'tonal_range': 150, 'subject_separation': 100}
        analytics_narrow = {'tonal_range': 50, 'subject_separation': 100}
        size_wide, _ = _calculate_glow_params(analytics_wide, 'laser_standard')
        size_narrow, _ = _calculate_glow_params(analytics_narrow, 'laser_standard')
        assert size_wide <= size_narrow
