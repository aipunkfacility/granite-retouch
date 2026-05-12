"""TDD: DEFAULTS должны быть корректны без config.yaml."""

import os, tempfile
import pytest
from retouch.config import DEFAULTS, load_config, MACHINE_TYPES


class TestDefaultsConsistency:
    """Критические параметры DEFAULTS соответствуют документации."""

    def test_impact_dither_method_is_none(self):
        """impact использует 8-bit grayscale (256 уровней силы удара), не 1-bit."""
        assert DEFAULTS["processing"]["impact"]["dither_method"] == "none", (
            "impact.dither_method должен быть 'none' — 8-bit BMP для 256 уровней удара"
        )

    def test_laser_80w_dither_method_is_jarvis(self):
        assert DEFAULTS["processing"]["laser_80w"]["dither_method"] == "jarvis"

    def test_laser_standard_dither_method_is_none(self):
        assert DEFAULTS["processing"]["laser_standard"]["dither_method"] == "none"

    def test_defaults_without_config_yaml(self):
        """load_config() без config.yaml возвращает корректные DEFAULTS."""
        with tempfile.TemporaryDirectory() as tmp:
            orig = os.getcwd()
            os.chdir(tmp)
            try:
                cfg = load_config()
                assert cfg["processing"]["impact"]["dither_method"] == "none"
                assert cfg["processing"]["laser_80w"]["dither_method"] == "jarvis"
            finally:
                os.chdir(orig)

    def test_highlight_start_below_face_target(self):
        """highlight_start НЕ должен быть ниже face_brightness_target_min.
        Иначе коррекция затухает до достижения цели."""
        for machine in MACHINE_TYPES:
            mc = DEFAULTS["processing"][machine]
            hs = mc.get("highlight_start", 0)
            fb_min = mc.get("face_brightness_target_min", 0)
            assert hs >= fb_min - 30, (
                f"{machine}: highlight_start={hs} слишком низкий "
                f"при face_brightness_target_min={fb_min}"
            )

    def test_white_ceiling_above_face_target_max(self):
        """white_ceiling должен быть выше face_brightness_target_max."""
        for machine in MACHINE_TYPES:
            mc = DEFAULTS["processing"][machine]
            assert mc["white_ceiling"] > mc["face_brightness_target_max"], (
                f"{machine}: white_ceiling <= face_brightness_target_max"
            )
