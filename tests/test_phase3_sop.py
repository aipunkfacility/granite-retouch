"""Тесты Фазы 3 — SOP-улучшения (FIX #11, #12).

FIX #11: USM threshold из конфига (SOP 3.1: 2-4)
FIX #12: shadow_floor для лазерных станков (SOP 5.1: black point 5-10)
"""

import copy
import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS, load_config


class TestUnsharpThreshold:
    """FIX #11: USM threshold из конфига (SOP 3.1: 2-4)."""

    def test_default_threshold_ge_2(self):
        """По умолчанию unsharp_threshold >= 2 для всех машин."""
        config = load_config()
        for machine in ("laser_standard", "laser_80w", "impact"):
            threshold = config["processing"][machine].get("unsharp_threshold", 0)
            assert threshold >= 2, \
                f"{machine}: unsharp_threshold должен быть >= 2 (SOP), got {threshold}"

    def test_default_threshold_le_8(self):
        """unsharp_threshold <= 8 (верхняя граница SOP)."""
        config = load_config()
        for machine in ("laser_standard", "laser_80w", "impact"):
            threshold = config["processing"][machine].get("unsharp_threshold", 0)
            assert threshold <= 8, \
                f"{machine}: unsharp_threshold должен быть <= 8, got {threshold}"


class TestLaserShadowFloor:
    """FIX #12: shadow_floor для лазерных станков (SOP 5.1: black point 5-10)."""

    def test_laser_80w_has_shadow_floor(self):
        """Laser 80W: shadow_floor >= 5."""
        config = load_config()
        floor = config["processing"]["laser_80w"].get("shadow_floor", 0)
        assert floor >= 5, f"laser_80w shadow_floor должен быть >= 5, got {floor}"

    def test_laser_standard_has_shadow_floor(self):
        """Laser standard: shadow_floor >= 5."""
        config = load_config()
        floor = config["processing"]["laser_standard"].get("shadow_floor", 0)
        assert floor >= 5, f"laser_standard shadow_floor должен быть >= 5, got {floor}"

    def test_impact_shadow_floor_unchanged(self):
        """Impact: shadow_floor = 8 (не изменился)."""
        config = load_config()
        floor = config["processing"]["impact"].get("shadow_floor", 0)
        assert floor == 8, f"impact shadow_floor должен быть 8, got {floor}"

    def test_shadow_floor_applied_for_laser_80w(self, tmp_path):
        """Shadow_floor применяется для laser_80w в пайплайне."""
        from retouch.processing.pipeline import process_steps

        # Создаём очень тёмное изображение с синим фоном
        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255  # синий фон
        arr[..., 3] = 255
        # Тёмный субъект в центре
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 10
        arr[ellipse, 1] = 8
        arr[ellipse, 2] = 6
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        config = copy.deepcopy(DEFAULTS)
        config["processing"]["laser_80w"]["shadow_floor"] = 5

        result = process_steps(input_path, machine_type="laser_80w", config=config)

        # Проверяем что shadow_floor был применён
        if result.subject_mask is not None and result.img_sharpened is not None:
            sharpened_arr = np.array(result.img_sharpened)
            mask_bool = np.array(result.subject_mask) > 128
            subject_pixels = sharpened_arr[mask_bool]
            below_floor = (subject_pixels < 5).sum()
            assert below_floor == 0, \
                f"Не должно быть пикселей < shadow_floor=5, found {below_floor}"
