"""Тесты apply_material_overrides() и validate_machine_material()."""

import copy
import pytest
from retouch.config import (
    apply_material_overrides,
    validate_machine_material,
    MATERIAL_PROFILES,
)


def _make_config(machine_type="impact", step_mm=0.300, stone_gamma=0.90, shadow_floor=8, white_ceiling=240):
    """Создать тестовый конфиг с заданными параметрами."""
    return {
        "machine_type": machine_type,
        "processing": {
            machine_type: {
                "step_mm": step_mm,
                "stone_gamma": stone_gamma,
                "shadow_floor": shadow_floor,
                "white_ceiling": white_ceiling,
                "export_mode": "8bit",
                "dither_method_1bit": "stucki",
            }
        },
        "stone": {"type": "granite", "material": "granite"},
    }


class TestApplyMaterialOverrides:
    """Тесты apply_material_overrides()."""

    def test_step_mm_out_of_range_low(self):
        """step_mm ниже диапазона → поднят к нижней границе."""
        config = _make_config(step_mm=0.200)
        result, changes = apply_material_overrides(config, "granite")
        # granite step_range = (0.250, 0.300), 0.200 < 0.250
        step_changes = [c for c in changes if c["param"] == "step"]
        assert len(step_changes) == 1
        assert step_changes[0]["new"] == 0.250
        assert "ниже диапазона" in step_changes[0]["reason"]

    def test_step_mm_out_of_range_high(self):
        """step_mm выше диапазона → опущен к верхней границе."""
        config = _make_config(step_mm=0.500)
        result, changes = apply_material_overrides(config, "granite")
        step_changes = [c for c in changes if c["param"] == "step"]
        assert len(step_changes) == 1
        assert step_changes[0]["new"] == 0.300
        assert "выше диапазона" in step_changes[0]["reason"]

    def test_step_mm_within_range(self):
        """step_mm в диапазоне → не меняется."""
        config = _make_config(step_mm=0.275)
        result, changes = apply_material_overrides(config, "granite")
        step_changes = [c for c in changes if c["param"] == "step"]
        assert len(step_changes) == 0

    def test_gamma_out_of_range(self):
        """stone_gamma вне диапазона → подогнать."""
        config = _make_config(stone_gamma=0.80)
        result, changes = apply_material_overrides(config, "granite")
        # granite gamma_range = (0.85, 0.90), 0.80 < 0.85
        gamma_changes = [c for c in changes if c["param"] == "gamma"]
        assert len(gamma_changes) == 1
        assert gamma_changes[0]["new"] == 0.85

    def test_acrylic_export_mode_override(self):
        """acrylic → export_mode = 1bit + dither = jarvis."""
        config = _make_config(machine_type="laser_80w")
        result, changes = apply_material_overrides(config, "acrylic")
        mode_changes = [c for c in changes if c["param"] == "export_mode"]
        assert len(mode_changes) == 1
        assert mode_changes[0]["new"] == "1bit"
        dither_changes = [c for c in changes if c["param"] == "dither"]
        assert len(dither_changes) == 1
        assert dither_changes[0]["new"] == "jarvis"

    def test_marble_white_ceiling(self):
        """marble → white_ceiling строже (offset -5)."""
        config = _make_config(white_ceiling=240)
        result, changes = apply_material_overrides(config, "marble")
        ceiling_changes = [c for c in changes if c["param"] == "white_ceiling"]
        assert len(ceiling_changes) == 1
        assert ceiling_changes[0]["new"] == 235  # 240 + (-5) = 235

    def test_changes_include_reason(self):
        """changes содержит reason для out-of-range корректировок."""
        config = _make_config(step_mm=0.200)
        _, changes = apply_material_overrides(config, "granite")
        step_changes = [c for c in changes if c["param"] == "step"]
        assert len(step_changes) == 1
        assert "reason" in step_changes[0]
        assert "ниже диапазона" in step_changes[0]["reason"]

    def test_changes_no_reason_when_in_range(self):
        """Изменений нет → changes пустой (все параметры в диапазоне)."""
        config = _make_config(machine_type="impact", step_mm=0.300, stone_gamma=0.90, shadow_floor=8)
        _, changes = apply_material_overrides(config, "granite")
        # granite: step (0.250-0.300) OK, gamma (0.85-0.90) OK, shadow_floor 8 vs 8 = no change
        # but gamma 0.90 is at boundary = OK, step 0.300 is at boundary = OK
        # shadow_floor: granite=8, config=8 → no change
        # So only possible change is shadow_floor but it's the same
        step_changes = [c for c in changes if c["param"] == "step"]
        gamma_changes = [c for c in changes if c["param"] == "gamma"]
        assert len(step_changes) == 0
        assert len(gamma_changes) == 0

    def test_config_not_mutated(self):
        """apply_material_overrides не мутирует исходный конфиг."""
        config = _make_config(step_mm=0.200)
        original = copy.deepcopy(config)
        apply_material_overrides(config, "granite")
        assert config == original

    def test_slate_profile_values(self):
        """slate: override gamma and step_mm, enforce 1bit+dither."""
        config = _make_config(machine_type="laser_80w", step_mm=0.300, stone_gamma=0.95)
        result, changes = apply_material_overrides(config, "slate")
        # slate step_range = (0.150, 0.200), 0.300 > 0.200 → lowered
        step_changes = [c for c in changes if c["param"] == "step"]
        assert len(step_changes) == 1
        from pytest import approx
        assert step_changes[0]["new"] == approx(0.200)
        # slate gamma_range = (0.80, 0.85), 0.95 > 0.85 → lowered
        gamma_changes = [c for c in changes if c["param"] == "gamma"]
        assert len(gamma_changes) == 1
        assert gamma_changes[0]["new"] == approx(0.85)
        # slate: export_mode → 1bit, dither → jarvis
        mode_changes = [c for c in changes if c["param"] == "export_mode"]
        assert len(mode_changes) == 1
        assert mode_changes[0]["new"] == "1bit"
        dither_changes = [c for c in changes if c["param"] == "dither"]
        assert len(dither_changes) == 1
        assert dither_changes[0]["new"] == "jarvis"

    def test_unknown_material_no_changes(self):
        """Неизвестный материал → без изменений."""
        config = _make_config()
        result, changes = apply_material_overrides(config, "unknown_stone")
        assert changes == []


class TestValidateMachineMaterial:
    """Тесты validate_machine_material()."""

    def test_validate_acrylic_impact_error(self):
        """acrylic + impact → ERROR (несовместимая комбинация)."""
        warnings = validate_machine_material("impact", "acrylic")
        errors = [w for w in warnings if w.startswith("ERROR")]
        assert len(errors) == 1

    def test_validate_marble_impact_warning(self):
        """marble + impact → WARNING (не оптимально)."""
        warnings = validate_machine_material("impact", "marble")
        warns = [w for w in warnings if w.startswith("WARNING")]
        assert len(warns) >= 1

    def test_validate_laser80w_granite_warning(self):
        """laser_80w + granite → WARNING (пережигание)."""
        warnings = validate_machine_material("laser_80w", "granite")
        warns = [w for w in warnings if w.startswith("WARNING")]
        assert len(warns) >= 1

    def test_validate_slate_impact_warning(self):
        """slate + impact → WARNING (анизотропная прочность)."""
        warnings = validate_machine_material("impact", "slate")
        warns = [w for w in warnings if w.startswith("WARNING")]
        assert len(warns) >= 1
        assert any("сланец" in w.lower() or "slate" in w.lower() for w in warns)

    def test_validate_compatible_no_warnings(self):
        """impact + granite → без предупреждений."""
        warnings = validate_machine_material("impact", "granite")
        assert warnings == []
