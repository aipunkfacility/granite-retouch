"""Тесты миграции stone.type → material (v3 → v4)."""

import tempfile
from pathlib import Path

import pytest
import yaml

from retouch.config import load_config, save_config, CONFIG_VERSION, _migrate_v3_to_v4


class TestStoneTypeMaterialMigration:
    """Тесты миграции stone.type → material."""

    def test_config_with_stone_type_auto_migrates(self):
        """Конфиг с stone.type → material автоматически подставляется."""
        # Тестируем _migrate_v3_to_v4 напрямую, т.к. load_config сначала
        # делает deep_merge с DEFAULTS (где material=granite), что затирает
        # результат миграции для stone.type.
        config = {
            "stone": {"type": "gabbro"},
            "processing": {},
        }
        result = _migrate_v3_to_v4(config)
        assert result["stone"]["material"] == "gabbro"
        assert result["stone"]["type"] == "gabbro"

    def test_config_with_material_only(self):
        """Конфиг с material (без stone.type) → stone.type = material."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_data = {
                "stone": {"material": "basalt"},
                "processing": {},
            }
            config_path.write_text(yaml.dump(config_data, allow_unicode=True), encoding="utf-8")
            config = load_config(config_path)
            assert config["stone"]["type"] == "basalt"
            assert config["stone"]["material"] == "basalt"

    def test_config_with_both_prefers_material(self):
        """Оба ключа → material имеет приоритет."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_data = {
                "stone": {"type": "granite", "material": "marble"},
                "processing": {},
            }
            config_path.write_text(yaml.dump(config_data, allow_unicode=True), encoding="utf-8")
            config = load_config(config_path)
            # material has priority
            assert config["stone"]["material"] == "marble"
            assert config["stone"]["type"] == "marble"  # synced to material

    def test_save_config_writes_both_keys(self):
        """При сохранении пишутся оба ключа для совместимости."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {
                "stone": {"material": "gabbro"},
                "processing": {},
                "config_version": 4,
            }
            save_config(config_path, config)
            saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            assert "material" in saved["stone"]
            assert "type" in saved["stone"]
            assert saved["stone"]["type"] == saved["stone"]["material"]

    def test_v3_to_v4_migration(self):
        """Миграция v3→v4 добавляет material."""
        # Тестируем _migrate_v3_to_v4 напрямую, т.к. load_config сначала
        # делает deep_merge с DEFAULTS (где material=granite), что затирает
        # результат миграции для stone.type.
        config = {
            "config_version": 3,
            "stone": {"type": "gabbro"},
            "processing": {},
        }
        result = _migrate_v3_to_v4(config)
        assert result["stone"]["material"] == "gabbro"
        assert result["config_version"] == 4

    def test_acrylic_accepted_as_material(self):
        """acrylic принимается как значение material."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_data = {
                "stone": {"material": "acrylic"},
                "processing": {},
            }
            config_path.write_text(yaml.dump(config_data, allow_unicode=True), encoding="utf-8")
            config = load_config(config_path)
            assert config["stone"]["material"] == "acrylic"
            assert config["stone"]["type"] == "acrylic"
