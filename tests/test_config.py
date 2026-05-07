"""Тесты конфигурации — загрузка, defaults, валидация."""

import copy
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from retouch.config import DEFAULTS, load_config, deep_merge, find_config_path, validate_config, MACHINE_TYPES


class TestDefaults:
    """Тесты встроенных defaults."""

    def test_defaults_has_processing(self):
        """DEFAULTS содержит секцию processing."""
        assert "processing" in DEFAULTS

    def test_defaults_has_laser_standard(self):
        """DEFAULTS содержит параметры laser_standard."""
        assert "laser_standard" in DEFAULTS["processing"]
        laser_standard = DEFAULTS["processing"]["laser_standard"]
        assert "glow_size_min" in laser_standard
        assert "glow_size_max" in laser_standard
        assert "brightness" in laser_standard
        assert "face_brightness_target_min" in laser_standard
        assert "face_brightness_target_max" in laser_standard
        assert "face_region_top" in laser_standard
        assert "highlight_start" in laser_standard

    def test_defaults_has_laser_80w(self):
        """DEFAULTS содержит параметры laser_80w."""
        assert "laser_80w" in DEFAULTS["processing"]
        laser_80w = DEFAULTS["processing"]["laser_80w"]
        assert "glow_size_min" in laser_80w
        assert "glow_size_max" in laser_80w
        assert "brightness" in laser_80w
        assert "face_brightness_target_min" in laser_80w
        assert "face_brightness_target_max" in laser_80w
        assert "face_region_top" in laser_80w
        assert "highlight_start" in laser_80w

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

    def test_laser_standard_glow_ranges_valid(self):
        """Laser Standard: glow_size_min < glow_size_max, glow_opacity_min < max."""
        laser_standard = DEFAULTS["processing"]["laser_standard"]
        assert laser_standard["glow_size_min"] < laser_standard["glow_size_max"]
        assert laser_standard["glow_opacity_min"] < laser_standard["glow_opacity_max"]

    def test_impact_glow_ranges_valid(self):
        """Impact: glow_size_min < glow_size_max, glow_opacity_min < max."""
        impact = DEFAULTS["processing"]["impact"]
        assert impact["glow_size_min"] < impact["glow_size_max"]
        assert impact["glow_opacity_min"] < impact["glow_opacity_max"]

    def test_face_brightness_target_ranges(self):
        """face_brightness_target_min < face_brightness_target_max для всех станков."""
        for mtype in MACHINE_TYPES:
            mc = DEFAULTS["processing"][mtype]
            assert mc["face_brightness_target_min"] < mc["face_brightness_target_max"], \
                f"{mtype}: min < max"


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
        base = {"processing": {"blue_threshold": 30, "laser_standard": {"brightness": 1.18}}}
        override = {"processing": {"laser_standard": {"brightness": 1.30}}}
        result = deep_merge(base, override)
        assert result["processing"]["blue_threshold"] == 30
        assert result["processing"]["laser_standard"]["brightness"] == 1.30

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
                "laser_standard": {
                    "brightness": 1.30,
                    "face_brightness_target": [220, 240],  # old list format
                },
            },
        }
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_file))
        assert config["processing"]["blue_threshold"] == 50
        assert config["processing"]["laser_standard"]["brightness"] == 1.30
        # Миграция: старый список → отдельные ключи
        assert config["processing"]["laser_standard"]["face_brightness_target_min"] == 220
        assert config["processing"]["laser_standard"]["face_brightness_target_max"] == 240
        assert "face_brightness_target" not in config["processing"]["laser_standard"]
        # deep_merge: defaults дополняются
        assert config["processing"]["laser_standard"]["glow_size_min"] == 40
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
                "laser_standard": {
                    "brightness": 1.50,
                },
            },
        }
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_file))
        config["processing"]["laser_standard"]["brightness"] = 999

        # DEFAULTS не должен мутировать
        assert DEFAULTS["processing"]["laser_standard"]["brightness"] == 1.18


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
        config["processing"]["laser_standard"]["glow_size_min"] = 100
        config["processing"]["laser_standard"]["glow_size_max"] = 50
        warnings = validate_config(config)
        assert any("glow_size_min > glow_size_max" in w for w in warnings)

    def test_glow_opacity_min_gt_max_warns(self):
        """glow_opacity_min > glow_opacity_max — предупреждение."""
        config = copy.deepcopy(DEFAULTS)
        config["processing"]["laser_standard"]["glow_opacity_min"] = 100
        config["processing"]["laser_standard"]["glow_opacity_max"] = 30
        warnings = validate_config(config)
        assert any("glow_opacity_min > glow_opacity_max" in w for w in warnings)

    def test_bad_brightness_warns(self):
        """brightness out of range produces a warning."""
        bad_config = deep_merge(DEFAULTS, {"processing": {"laser_standard": {"brightness": 9.99}}})
        warnings = validate_config(bad_config)
        assert len(warnings) > 0

    def test_impact_inverted_ranges_warn(self):
        """Impact inverted glow ranges also produce warnings."""
        config = copy.deepcopy(DEFAULTS)
        config["processing"]["impact"]["glow_size_min"] = 100
        config["processing"]["impact"]["glow_size_max"] = 5
        warnings = validate_config(config)
        assert any("glow_size_min > glow_size_max" in w for w in warnings)


class TestDeepMergeAdvanced:
    """Additional deep_merge tests for Phase 4."""

    def test_deep_merge_list_override(self):
        """deep_merge: lists are replaced entirely, not merged."""
        base = {"processing": {"laser_standard": {"some_list": [200, 230]}}}
        override = {"processing": {"laser_standard": {"some_list": [185, 210]}}}
        result = deep_merge(base, override)
        assert result["processing"]["laser_standard"]["some_list"] == [185, 210]

    def test_deep_merge_does_not_mutate_defaults(self):
        """deep_merge does not mutate DEFAULTS (A9)."""
        original = copy.deepcopy(DEFAULTS)
        override = {"processing": {"laser_standard": {"brightness": 9.99}}}
        result = deep_merge(DEFAULTS, override)

        # DEFAULTS unchanged
        assert DEFAULTS["processing"]["laser_standard"]["brightness"] == original["processing"]["laser_standard"]["brightness"]
        # Result contains override
        assert result["processing"]["laser_standard"]["brightness"] == 9.99
        # Other laser_standard keys preserved from DEFAULTS
        assert "glow_size_min" in result["processing"]["laser_standard"]

    def test_partial_yaml_merged_with_defaults(self):
        """Partial YAML is supplemented by DEFAULTS via deep_merge."""
        partial = {"processing": {"laser_standard": {"brightness": 1.30}}}
        result = deep_merge(DEFAULTS, partial)
        assert result["processing"]["laser_standard"]["brightness"] == 1.30
        assert "glow_size_min" in result["processing"]["laser_standard"]
        assert "vignette" in result

    def test_deep_merge_nested_dicts_correctly(self):
        """deep_merge correctly merges nested dicts."""
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99}}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": {"c": 99, "d": 3}}

    def test_deep_merge_empty_override(self):
        """deep_merge with empty override returns copy of base."""
        base = {"processing": {"blue_threshold": 30}}
        result = deep_merge(base, {})
        assert result == base
        assert result is not base  # Must be a copy

    def test_deep_merge_new_keys_added(self):
        """deep_merge adds new keys from override."""
        base = {"a": 1}
        override = {"b": 2}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 2}


class TestPydanticModel:
    """Tests for Pydantic model and DEFAULTS consistency (A9)."""

    def test_defaults_validate_no_warnings(self):
        """DEFAULTS pass validation without warnings."""
        warnings = validate_config(DEFAULTS)
        assert len(warnings) == 0, f"DEFAULTS have warnings: {warnings}"

    @pytest.mark.skipif(
        not __import__("retouch.config", fromlist=["HAS_PYDANTIC"]).HAS_PYDANTIC,
        reason="Pydantic not installed",
    )
    def test_pydantic_model_available(self):
        """Pydantic model is available when pydantic is installed."""
        from retouch.config import RetouchConfig
        config = RetouchConfig()
        assert config.processing.laser_standard.brightness > 0

    @pytest.mark.skipif(
        not __import__("retouch.config", fromlist=["HAS_PYDANTIC"]).HAS_PYDANTIC,
        reason="Pydantic not installed",
    )
    def test_defaults_match_pydantic(self):
        """DEFAULTS and Pydantic model contain matching default values (A9)."""
        from retouch.config import RetouchConfig
        pydantic_defaults = RetouchConfig().model_dump()
        # Compare keys present in both sources
        for machine in MACHINE_TYPES:
            for key in DEFAULTS["processing"][machine]:
                if key in pydantic_defaults["processing"][machine]:
                    assert DEFAULTS["processing"][machine][key] == pydantic_defaults["processing"][machine][key], \
                        f"DEFAULTS mismatch for processing.{machine}.{key}"


class TestConfigMachineTypes:
    """P4: config поддерживает 3 machine_type (этап 8)."""

    def test_laser_80w_config_exists(self):
        """Секция laser_80w присутствует в DEFAULTS."""
        assert "laser_80w" in DEFAULTS["processing"]

    def test_laser_80w_face_target(self):
        """Laser 80W target = 135-160."""
        cfg = DEFAULTS["processing"]["laser_80w"]
        assert cfg["face_brightness_target_min"] == 135
        assert cfg["face_brightness_target_max"] == 160

    def test_impact_face_target(self):
        """Impact target = 120-145."""
        cfg = DEFAULTS["processing"]["impact"]
        assert cfg["face_brightness_target_min"] == 120
        assert cfg["face_brightness_target_max"] == 145

    def test_laser_standard_renamed(self):
        """Старый ключ 'laser' заменён на 'laser_standard'."""
        assert "laser" not in DEFAULTS["processing"]
        assert "laser_standard" in DEFAULTS["processing"]

    def test_all_machine_types_have_glow_ranges(self):
        """Все machine_type имеют корректные glow-диапазоны."""
        for mtype in MACHINE_TYPES:
            mc = DEFAULTS["processing"][mtype]
            assert mc["glow_size_min"] < mc["glow_size_max"], \
                f"{mtype}: glow_size_min ({mc['glow_size_min']}) >= glow_size_max ({mc['glow_size_max']})"
            assert mc["glow_opacity_min"] < mc["glow_opacity_max"], \
                f"{mtype}: glow_opacity_min ({mc['glow_opacity_min']}) >= glow_opacity_max ({mc['glow_opacity_max']})"
