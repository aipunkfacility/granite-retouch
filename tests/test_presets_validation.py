"""TDD: пресеты должны содержать физически корректные параметры."""

import pytest
import yaml
from pathlib import Path
from retouch.config import DEFAULTS, MACHINE_TYPES, deep_merge, _migrate_face_target

PRESETS_DIR = Path(__file__).parent.parent / "presets"
PRESET_FILES = list(PRESETS_DIR.glob("*.yaml"))


@pytest.mark.parametrize("preset_path", PRESET_FILES, ids=lambda p: p.stem)
class TestPresetPhysicalConstraints:

    def _load_merged(self, preset_path):
        """Загрузить пресет поверх DEFAULTS (как делает реальный пайплайн)."""
        with open(preset_path, encoding="utf-8") as f:
            preset = yaml.safe_load(f)
        merged = deep_merge(DEFAULTS, preset)
        return _migrate_face_target(merged)

    def test_no_brightness_key(self, preset_path):
        """Пресеты не должны содержать устаревший ключ 'brightness'."""
        with open(preset_path, encoding="utf-8") as f:
            preset = yaml.safe_load(f)
        for machine in MACHINE_TYPES:
            mc = preset.get("processing", {}).get(machine, {})
            assert "brightness" not in mc, (
                f"{preset_path.name}: найден устаревший ключ 'brightness' "
                f"в {machine}. Используйте 'stone_gamma'."
            )

    def test_face_brightness_in_physical_range(self, preset_path):
        """face_brightness_target должен быть в допустимом физическом диапазоне."""
        PHYSICAL_RANGES = {
            "laser_standard": (200, 255),
            "laser_80w": (150, 235),   # 150 минимум: Stanzone/Mirtels 80W используют 160
            "impact": (165, 240),      # эталон P25=168, min=170 с запасом
        }
        cfg = self._load_merged(preset_path)
        for machine, (lo, hi) in PHYSICAL_RANGES.items():
            mc = cfg["processing"].get(machine, {})
            if not mc:
                continue
            fb_min = mc.get("face_brightness_target_min", 0)
            fb_max = mc.get("face_brightness_target_max", 0)
            assert fb_min >= lo, (
                f"{preset_path.name}/{machine}: face_brightness_target_min={fb_min} "
                f"ниже физического минимума {lo}"
            )
            assert fb_max <= hi, (
                f"{preset_path.name}/{machine}: face_brightness_target_max={fb_max} "
                f"выше физического максимума {hi}"
            )

    def test_export_mode_explicit(self, preset_path):
        """impact-пресеты должны явно задавать export_mode."""
        with open(preset_path, encoding="utf-8") as f:
            preset = yaml.safe_load(f)
        impact = preset.get("processing", {}).get("impact", {})
        if impact:  # только если пресет затрагивает impact
            has_export = "export_mode" in impact
            assert has_export, (
                f"{preset_path.name}: impact-пресет должен содержать 'export_mode'"
            )

    def test_stone_gamma_range(self, preset_path):
        """stone_gamma должен быть в допустимом диапазоне [0.70, 1.10]."""
        with open(preset_path, encoding="utf-8") as f:
            preset = yaml.safe_load(f)
        for machine in MACHINE_TYPES:
            mc = preset.get("processing", {}).get(machine, {})
            if "stone_gamma" in mc:
                gamma = mc["stone_gamma"]
                assert 0.70 <= gamma <= 1.10, (
                    f"{preset_path.name}/{machine}: stone_gamma={gamma} вне диапазона [0.70, 1.10]"
                )

    def test_critical_params_present(self, preset_path):
        """Пресеты должны явно содержать критические параметры."""
        CRITICAL = {
            "laser_standard": ["white_ceiling", "export_mode"],
            "laser_80w": ["white_ceiling", "export_mode"],
            "impact": ["white_ceiling", "export_mode", "shadow_floor"],
        }
        with open(preset_path, encoding="utf-8") as f:
            preset = yaml.safe_load(f)
        for machine, required_keys in CRITICAL.items():
            mc = preset.get("processing", {}).get(machine, {})
            if not mc:
                continue
            for key in required_keys:
                assert key in mc, (
                    f"{preset_path.name}/{machine}: отсутствует критический параметр '{key}'"
                )
