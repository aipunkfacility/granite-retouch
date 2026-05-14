"""Интеграционные тесты: пресеты + материал + валидация."""

import pytest
import yaml
from pathlib import Path

from retouch.config import (
    load_config,
    apply_material_overrides,
    validate_machine_material,
    deep_merge,
    find_config_path,
)
from retouch.presets_catalog import PRESET_CATALOG


def _load_preset(preset_name: str) -> dict:
    """Загрузить пресет из YAML-файла."""
    config_path = find_config_path()
    if config_path:
        presets_dir = config_path.parent / "presets"
    else:
        presets_dir = Path.cwd() / "presets"

    preset_file = presets_dir / f"{preset_name}.yaml"
    if not preset_file.is_file():
        pytest.skip(f"Пресет {preset_name} не найден: {preset_file}")

    with open(preset_file, "r", encoding="utf-8") as f:
        preset_config = yaml.safe_load(f) or {}

    return preset_config


class TestPresetCatalog:
    """Тесты PRESET_CATALOG."""

    def test_catalog_contains_all_presets(self):
        """PRESET_CATALOG содержит все 11 пресетов."""
        assert len(PRESET_CATALOG) == 11  # 3 technology + 8 machine

    def test_catalog_has_required_fields(self):
        """Каждый пресет в каталоге содержит обязательные поля."""
        for name, meta in PRESET_CATALOG.items():
            assert "label" in meta, f"Missing 'label' in {name}"
            assert "category" in meta, f"Missing 'category' in {name}"
            assert "machine_type" in meta, f"Missing 'machine_type' in {name}"

    def test_catalog_categories(self):
        """Категории — только technology и machine."""
        for name, meta in PRESET_CATALOG.items():
            assert meta["category"] in ("technology", "machine"), \
                f"Invalid category '{meta['category']}' in {name}"


class TestPresetYAML:
    """Тесты YAML-файлов пресетов."""

    @pytest.mark.parametrize("preset_name", list(PRESET_CATALOG.keys()))
    def test_preset_yaml_parses(self, preset_name):
        """Каждый YAML-пресет парсится без ошибок."""
        config = _load_preset(preset_name)
        assert isinstance(config, dict), f"Пресет {preset_name} не dict"

    @pytest.mark.parametrize("preset_name", list(PRESET_CATALOG.keys()))
    def test_preset_has_processing(self, preset_name):
        """Каждый пресет содержит processing с правильным machine_type."""
        config = _load_preset(preset_name)
        assert "processing" in config, f"Пресет {preset_name} не содержит 'processing'"
        meta = PRESET_CATALOG[preset_name]
        mt = meta["machine_type"]
        assert mt in config["processing"], \
            f"Пресет {preset_name} не содержит processing.{mt}"

    def test_stanzone_laser_1bit_is_1bit(self):
        """stanzone-laser-1bit содержит export_mode: 1bit."""
        config = _load_preset("stanzone-laser-1bit")
        assert config["processing"]["laser_80w"]["export_mode"] == "1bit"
        assert config["processing"]["laser_80w"]["dither_method_1bit"] == "jarvis"

    def test_mirtels_impact_step_mm(self):
        """Mirtels ударный: step_mm = 0.24 (105.8 dpi по мануалу)."""
        config = _load_preset("mirtels-impact")
        assert config["processing"]["impact"]["step_mm"] == 0.24

    def test_preset_plus_material(self):
        """--preset mirtels-impact --material gabbro → автокоррекция step."""
        base_config = load_config()
        preset_config = _load_preset("mirtels-impact")
        config = deep_merge(base_config, preset_config)
        config["machine_type"] = "impact"

        config, changes = apply_material_overrides(config, "gabbro")
        # gabbro step_range = (0.275, 0.350), mirtels default = 0.24
        # 0.24 < 0.275 → поднят до 0.275
        step_changes = [c for c in changes if c["param"] == "step"]
        assert len(step_changes) == 1
        assert step_changes[0]["new"] == 0.275
        assert "ниже диапазона" in step_changes[0]["reason"]

    def test_acrylic_impact_blocked(self):
        """acrylic + impact → валидация блокирует выполнение."""
        warnings = validate_machine_material("impact", "acrylic")
        errors = [w for w in warnings if w.startswith("ERROR")]
        assert len(errors) == 1
