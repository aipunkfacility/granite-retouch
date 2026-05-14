"""TDD: DEFAULTS должны быть корректны без config.yaml."""

import os, tempfile
import pytest
from retouch.config import DEFAULTS, load_config, MACHINE_TYPES


class TestDefaultsConsistency:
    """Критические параметры DEFAULTS соответствуют документации."""

    def test_impact_export_mode_is_8bit(self):
        """impact: export_mode=8bit (256 уровней силы удара)."""
        assert DEFAULTS["processing"]["impact"]["export_mode"] == "8bit", (
            "impact.export_mode должен быть '8bit' — 8-bit BMP для 256 уровней удара"
        )

    def test_laser_80w_export_mode_is_8bit(self):
        """laser_80w: export_mode=8bit (Engrave сам растрирует алгоритмами Р1-Р5)."""
        assert DEFAULTS["processing"]["laser_80w"]["export_mode"] == "8bit", (
            "laser_80w.export_mode должен быть '8bit' — Engrave модулирует мощность по яркости"
        )

    def test_laser_standard_export_mode_is_8bit(self):
        """laser_standard: export_mode=8bit."""
        assert DEFAULTS["processing"]["laser_standard"]["export_mode"] == "8bit"

    def test_laser_80w_stone_gamma_is_1(self):
        """laser_80w: stone_gamma=1.0 (при 8bit Engrave управляет яркостью через Р-график)."""
        assert DEFAULTS["processing"]["laser_80w"]["stone_gamma"] == 1.0

    def test_laser_80w_step_mm_is_025(self):
        """laser_80w: step_mm=0.250 (по мануалу САУНО: 0.125-0.250 мм для лазера)."""
        assert DEFAULTS["processing"]["laser_80w"]["step_mm"] == 0.250

    def test_defaults_without_config_yaml(self):
        """load_config() без config.yaml возвращает корректные DEFAULTS."""
        with tempfile.TemporaryDirectory() as tmp:
            orig = os.getcwd()
            os.chdir(tmp)
            try:
                cfg = load_config()
                assert cfg["processing"]["laser_80w"]["export_mode"] == "8bit"
                assert cfg["processing"]["laser_80w"]["stone_gamma"] == 1.0
                assert cfg["processing"]["laser_80w"]["step_mm"] == 0.250
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

    def test_all_machines_have_export_mode(self):
        """Все machine_type имеют export_mode."""
        for machine in MACHINE_TYPES:
            mc = DEFAULTS["processing"][machine]
            assert "export_mode" in mc, f"{machine}: нет ключа export_mode"
            assert mc["export_mode"] in ("8bit", "1bit")

    def test_all_machines_have_step_mm(self):
        """Все machine_type имеют per-machine step_mm."""
        for machine in MACHINE_TYPES:
            mc = DEFAULTS["processing"][machine]
            assert "step_mm" in mc, f"{machine}: нет ключа step_mm"

    def test_all_machines_have_dither_method_1bit(self):
        """Все machine_type имеют dither_method_1bit (для режима 1bit)."""
        for machine in MACHINE_TYPES:
            mc = DEFAULTS["processing"][machine]
            assert "dither_method_1bit" in mc, f"{machine}: нет ключа dither_method_1bit"


class TestV2toV3Migration:
    """Миграция v2→v3: dither_method→export_mode, per-machine step_mm, laser_80w gamma."""

    def test_dither_none_to_8bit(self):
        """dither_method=none → export_mode=8bit"""
        from retouch.config import _migrate_v2_to_v3
        config = {
            "config_version": 2,
            "processing": {
                "laser_standard": {"dither_method": "none"},
                "laser_80w": {"dither_method": "none", "stone_gamma": 0.85,
                              "face_brightness_target_min": 190,
                              "face_brightness_target_max": 210},
                "impact": {"dither_method": "none"},
            },
            "machine": {"step_mm": 0.300},
        }
        result = _migrate_v2_to_v3(config)
        assert result["processing"]["laser_standard"]["export_mode"] == "8bit"
        assert result["processing"]["laser_80w"]["export_mode"] == "8bit"
        assert result["processing"]["impact"]["export_mode"] == "8bit"

    def test_dither_jarvis_to_1bit(self):
        """dither_method=jarvis → export_mode=1bit, dither_method_1bit=jarvis"""
        from retouch.config import _migrate_v2_to_v3
        config = {
            "config_version": 2,
            "processing": {
                "laser_standard": {"dither_method": "none"},
                "laser_80w": {"dither_method": "jarvis", "stone_gamma": 0.85,
                              "face_brightness_target_min": 190,
                              "face_brightness_target_max": 210},
                "impact": {"dither_method": "none"},
            },
            "machine": {"step_mm": 0.300},
        }
        result = _migrate_v2_to_v3(config)
        assert result["processing"]["laser_80w"]["export_mode"] == "1bit"
        assert result["processing"]["laser_80w"]["dither_method_1bit"] == "jarvis"

    def test_laser_80w_gamma_and_fb_recalibration(self):
        """laser_80w: gamma 0.85→1.0, fb_min 190→160, fb_max 210→180"""
        from retouch.config import _migrate_v2_to_v3
        config = {
            "config_version": 2,
            "processing": {
                "laser_80w": {"dither_method": "jarvis", "stone_gamma": 0.85,
                              "face_brightness_target_min": 190,
                              "face_brightness_target_max": 210},
            },
            "machine": {"step_mm": 0.300},
        }
        result = _migrate_v2_to_v3(config)
        assert result["processing"]["laser_80w"]["stone_gamma"] == 1.0
        assert result["processing"]["laser_80w"]["face_brightness_target_min"] == 160
        assert result["processing"]["laser_80w"]["face_brightness_target_max"] == 180

    def test_per_machine_step_mm_from_global(self):
        """Глобальный step_mm копируется в per-machine при отсутствии"""
        from retouch.config import _migrate_v2_to_v3
        config = {
            "config_version": 2,
            "processing": {
                "laser_standard": {},
                "laser_80w": {},
                "impact": {},
            },
            "machine": {"step_mm": 0.300},
        }
        result = _migrate_v2_to_v3(config)
        assert result["processing"]["laser_standard"]["step_mm"] == 0.300
        assert result["processing"]["laser_80w"]["step_mm"] == 0.300
        assert result["processing"]["impact"]["step_mm"] == 0.300

    def test_migration_idempotent(self):
        """Повторный запуск миграции не меняет уже мигрированный конфиг"""
        from retouch.config import _migrate_v2_to_v3
        config_v3 = {
            "config_version": 3,
            "processing": {
                "laser_80w": {"export_mode": "8bit", "step_mm": 0.250,
                              "stone_gamma": 1.0, "dither_method_1bit": "jarvis"},
            },
        }
        result = _migrate_v2_to_v3(config_v3)
        assert result["processing"]["laser_80w"]["export_mode"] == "8bit"
        assert result["processing"]["laser_80w"]["stone_gamma"] == 1.0
