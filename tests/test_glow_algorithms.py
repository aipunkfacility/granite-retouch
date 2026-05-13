"""Тесты алгоритмов glow — outer glow, inner glow, glow_style."""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from retouch.processing.glow import (
    apply_glow,
    apply_outer_glow,
    apply_inner_glow_algorithm,
)


class TestOuterGlow:
    """Outer glow: свечение наружу от контура субъекта."""

    def test_outer_glow_brightens_edges(self):
        """Outer glow делает край субъекта светлее."""
        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([50, 50, 149, 149], fill=255)

        result = apply_outer_glow(gray, mask, glow_size=20, glow_opacity=0.35)
        result_arr = np.array(result)

        edge_pixels = result_arr[45:55, 95:105]
        assert edge_pixels.mean() > 80, "Outer glow должен делать край светлее"

    def test_outer_glow_does_not_pollute_background(self):
        """Outer glow не загрязняет далёкий фон."""
        gray = Image.new("L", (200, 200), 60)
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle([60, 60, 139, 139], fill=255)

        result = apply_outer_glow(gray, mask, glow_size=20, glow_opacity=0.50)
        result_arr = np.array(result)

        # Далёкий угол — не должен значительно измениться
        corner = result_arr[:10, :10]
        assert corner.mean() < 70, "Далёкий фон не должен загрязняться"


class TestInnerGlowAlgorithm:
    """Inner glow: свечение внутрь от контура субъекта."""

    def test_inner_glow_brightens_inner_edge(self):
        """Inner glow делает внутренний край субъекта светлее."""
        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([50, 50, 149, 149], fill=255)

        result = apply_inner_glow_algorithm(gray, mask, glow_size=20, glow_opacity=0.80)
        result_arr = np.array(result)

        edge_pixel = result_arr[55, 100]  # внутренний край
        center_pixel = result_arr[100, 100]  # центр

        assert edge_pixel > 80, f"Внутренний край должен быть светлее 80, got {edge_pixel}"
        assert center_pixel < 200, f"Центр не должен засвечиваться, got {center_pixel}"

    def test_inner_glow_edge_brighter_than_center(self):
        """Внутренний край светлее центра."""
        gray = Image.new("L", (200, 200), 60)
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle([40, 40, 159, 159], fill=255)

        result = apply_inner_glow_algorithm(gray, mask, glow_size=20, glow_opacity=0.80)
        result_arr = np.array(result)

        edge = result_arr[42:48, 42:48]
        center = result_arr[90:110, 90:110]

        assert edge.mean() > center.mean(), \
            "Внутренний край должен быть светлее центра"


class TestGlowStyleConfig:
    """glow_style из конфига: 'outer' (legacy) или 'inner'."""

    def test_glow_style_outer_backward_compat(self):
        """glow_style='outer' даёт outer glow (обратная совместимость)."""
        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([50, 50, 149, 149], fill=255)

        machine_cfg = {"glow_size_min": 20, "glow_size_max": 20,
                       "glow_opacity_min": 35, "glow_opacity_max": 35,
                       "glow_style": "outer"}

        result, glow_size, glow_opacity = apply_glow(
            gray, mask, machine_cfg,
            glow_size_override=20, glow_opacity_override=35,
            glow_style="outer",
        )

        assert glow_size == 20
        assert abs(glow_opacity - 0.35) < 0.01
        result_arr = np.array(result)
        assert result_arr.mean() > 80, "Outer glow должен осветлять"

    def test_glow_style_inner(self):
        """glow_style='inner' использует inner glow алгоритм."""
        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([50, 50, 149, 149], fill=255)

        machine_cfg = {"glow_size_min": 20, "glow_size_max": 20,
                       "glow_opacity_min": 35, "glow_opacity_max": 35,
                       "glow_style": "inner"}

        result, glow_size, glow_opacity = apply_glow(
            gray, mask, machine_cfg,
            glow_size_override=20, glow_opacity_override=80,
            glow_style="inner",
        )

        result_arr = np.array(result)
        assert result_arr.max() > 80, "Inner glow должен осветлять"
