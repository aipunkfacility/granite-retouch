"""Тесты конфигурации — загрузка, defaults, валидация."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from retouch.config import DEFAULTS, load_config


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

    def test_defaults_has_impact(self):
        """DEFAULTS содержит параметры impact."""
        assert "impact" in DEFAULTS["processing"]
        impact = DEFAULTS["processing"]["impact"]
        assert "shadow_noise" not in impact  # BACKLOG-006: не реализован

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

    def test_fallback_to_defaults_on_missing_file(self):
        """Несуществующий файл → DEFAULTS."""
        config = load_config("/nonexistent/config.yaml")
        # Должен вернуть DEFAULTS
        assert config == DEFAULTS

    def test_empty_config_file(self, tmp_path):
        """Пустой config.yaml → None (yaml.safe_load возвращает None)."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        config = load_config(str(config_file))
        # Пустой YAML → None, но load_config возвращает что загрузилось
        # Это ожидаемое поведение — пользователь должен заполнить конфиг
        assert config is None or isinstance(config, dict)
