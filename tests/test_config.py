"""Тесты конфигурации — загрузка, defaults, валидация."""

import copy
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from retouch.config import DEFAULTS, load_config, deep_merge, find_config_path, validate_config


class TestDefaults:
    """Тесты встроенных defaults."""

    def test_defaults_has_processing(self):
        """DEFAULTS содержит секцию processing."""
        assert "processing" in DEFAULTS

    def test_defaults_has_laser(self):
        """DEFAULTS содержит параметры laser."""
        assert "laser" in DEFAULTS["processing"]
        laser = DEFAULTS["processing"]["laser"]
        assert "glow_size_min" in laser
        assert "glow_size_max" in laser
        assert "brightness" in laser
        assert "face_brightness_target" in laser
        assert "face_region_top" in laser
        assert "highlight_start" in laser

    def test_defaults_has_impact(self):
        """DEFAULTS содержит параметры impact."""
        assert "impact" in DEFAULTS["processing"]
        impact = DEFAULTS["processing"]["impact"]
        assert "shadow_noise" not in impact  # BACKLOG-006: не реализован
        assert "face_region_top" in impact
        assert "highlight_start" in impact

    def test_defaults_has_vignette(self):
        """DEFAULTS содержит параметры виньетки."""
        assert "vignette" in DEFAULTS
        vign = DEFAULTS["vignette"]
        for key in ["vertical_offset", "vertical_diameter", "blur_radius",
                     "headroom", "horizontal_oversize"]:
            assert key in vign, f"Виньетка: нет ключа {key}"

    def test_laser_glow_ranges_valid(self):
        """Laser: glow_size_min < glow_size_max, glow_opacity_min < max."""
        laser = DEFAULTS["processing"]["laser"]
        assert laser["glow_size_min"] < laser["glow_size_max"]
        assert laser["glow_opacity_min"] < laser["glow_opacity_max"]

    def test_impact_glow_ranges_valid(self):
        """Impact: glow_size_min < glow_size_max, glow_opacity_min < max."""
        impact = DEFAULTS["processing"]["impact"]
        assert impact["glow_size_min"] < impact["glow_size_max"]
        assert impact["glow_opacity_min"] < impact["glow_opacity_max"]

    def test_face_brightness_target_ranges(self):
        """face_brightness_target: min < max для обоих станков."""
        for mtype in ["laser", "impact"]:
            target = DEFAULTS["processing"][mtype]["face_brightness_target"]
            assert len(target) == 2, f"{mtype}: target должен быть [min, max]"
            assert target[0] < target[1], f"{mtype}: min < max"


class TestDeepMerge:
    """Тесты deep_merge()."""

    def test_simple_merge(self):
        """override побеждает."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """Вложенные dict сливаются рекурсивно."""
        base = {"processing": {"blue_threshold": 30, "laser": {"brightness": 1.18}}}
        override = {"processing": {"laser": {"brightness": 1.30}}}
        result = deep_merge(base, override)
        assert result["processing"]["blue_threshold"] == 30
        assert result["processing"]["laser"]["brightness"] == 1.30

    def test_base_not_mutated(self):
        """deep_merge не мутирует base."""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = deep_merge(base, override)
        assert "c" not in base["a"], "base не должен мутировать"
        assert result["a"]["c"] == 2

    def test_override_dict_replaces_non_dict(self):
        """override dict заменяет non-dict значение."""
        base = {"a": 1}
        override = {"a": {"nested": True}}
        result = deep_merge(base, override)
        assert result["a"] == {"nested": True}


class TestLoadConfig:
    """Тесты загрузки конфигурации из файла."""

    def test_load_from_file(self, tmp_path):
        """Загрузка конфигурации из указанного файла."""
        config_data = {
            "processing": {
                "blue_threshold": 50,
                "laser": {
                    "brightness": 1.30,
                    "face_brightness_target": [220, 240],
                },
            },
        }
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_file))
        assert config["processing"]["blue_threshold"] == 50
        assert config["processing"]["laser"]["brightness"] == 1.30
        # deep_merge: defaults дополняются
        assert config["processing"]["laser"]["glow_size_min"] == 40
        assert "vignette" in config

    def test_fallback_to_defaults_on_missing_file(self):
        """Несуществующий файл → DEFAULTS (deep copy)."""
        config = load_config("/nonexistent/config.yaml")
        # Должен вернуть deepcopy(DEFAULTS)
        assert config["processing"]["blue_threshold"] == DEFAULTS["processing"]["blue_threshold"]

    def test_empty_config_file(self, tmp_path):
        """Пустой config.yaml → DEFAULTS (deep_merge(DEFAULTS, {}))."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        config = load_config(str(config_file))
        assert isinstance(config, dict)
        assert config["processing"]["blue_threshold"] == 30

    def test_result_not_mutate_defaults(self, tmp_path):
        """Мутация результата load_config не мутирует DEFAULTS."""
        config_data = {
            "processing": {
                "laser": {
                    "brightness": 1.50,
                },
            },
        }
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_file))
        config["processing"]["laser"]["brightness"] = 999

        # DEFAULTS не должен мутировать
        assert DEFAULTS["processing"]["laser"]["brightness"] == 1.18


class TestFindConfigPath:
    """Тесты find_config_path()."""

    def test_returns_path_or_none(self):
        """find_config_path возвращает Path или None."""
        path = find_config_path()
        assert path is None or isinstance(path, Path)


class TestValidateConfig:
    """Тесты validate_config()."""

    def test_valid_config_no_warnings(self):
        """Валидный конфиг не даёт предупреждений."""
        warnings = validate_config(DEFAULTS)
        assert len(warnings) == 0, f"Unexpected warnings: {warnings}"

    def test_glow_size_min_gt_max_warns(self):
        """glow_size_min > glow_size_max — предупреждение."""
        config = copy.deepcopy(DEFAULTS)
        config["processing"]["laser"]["glow_size_min"] = 100
        config["processing"]["laser"]["glow_size_max"] = 50
        warnings = validate_config(config)
        assert any("glow_size_min > glow_size_max" in w for w in warnings)

    def test_glow_opacity_min_gt_max_warns(self):
        """glow_opacity_min > glow_opacity_max — предупреждение."""
        config = copy.deepcopy(DEFAULTS)
        config["processing"]["laser"]["glow_opacity_min"] = 100
        config["processing"]["laser"]["glow_opacity_max"] = 30
        warnings = validate_config(config)
        assert any("glow_opacity_min > glow_opacity_max" in w for w in warnings)
