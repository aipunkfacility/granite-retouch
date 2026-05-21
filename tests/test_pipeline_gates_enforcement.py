"""Тесты gates enforcement — ослабление параметров и warnings.

Проверяют что quality gates реально влияют на пайплайн:
- face_dark_small → face_correction_factor == 1.0 + warning
- variance_loss → warning в result.warnings (или gate_state)
"""

from copy import deepcopy

import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS
from retouch.processing.core.pipeline import process_steps


class TestGatesEnforcement:
    """Gates enforcement: ослабление параметров и warnings."""

    @staticmethod
    def _make_test_image(tmp_path, width=512, height=512):
        """Синтетическое изображение с хромакеем."""
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        cx, cy = width // 2, height // 2
        rx, ry = int(width * 0.25), int(height * 0.30)
        y_c, x_c = np.ogrid[:height, :width]
        ellipse = ((x_c - cx) / rx) ** 2 + ((y_c - cy) / ry) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255
        img = Image.fromarray(arr)
        path = str(tmp_path / "input.png")
        img.save(path, "PNG")
        return path

    @staticmethod
    def _make_config_with_gate_threshold(gate_name, threshold):
        """Создать конфиг с одним quality gate threshold."""
        config = deepcopy(DEFAULTS)
        config.setdefault("processing", {}).setdefault("quality_gates", {})
        config["processing"]["quality_gates"][gate_name] = threshold
        return config

    def test_face_dark_small_skips_correction(self, tmp_path):
        """face_dark_small gate → correction не применяется (factor == 1.0)."""
        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        arr[100:400, 150:350] = [200, 200, 200, 255]
        img = Image.fromarray(arr)
        bright_path = str(tmp_path / "bright.png")
        img.save(bright_path, "PNG")

        config = self._make_config_with_gate_threshold("face_dark_small_threshold", 100.0)

        result = process_steps(
            bright_path, machine_type="laser_standard",
            config=config,
        )

        assert result.face_correction_factor == 1.0
        gate_warnings = [
            w for w in result.warnings
            if "face_dark" in w.lower() or "face_correction skipped" in w.lower()
        ]
        assert len(gate_warnings) > 0

    def test_variance_loss_gate_warns(self, tmp_path):
        """variance_loss gate > 35% → warning в result.warnings или gate_state."""
        input_path = self._make_test_image(tmp_path)
        config = self._make_config_with_gate_threshold("variance_loss_threshold", 0.0)

        result = process_steps(
            input_path, machine_type="laser_standard",
            config=config,
        )

        gate_warnings = [w for w in result.warnings if "variance_loss" in w.lower()]
        if len(gate_warnings) > 0:
            return

        gate_state_warnings = [
            w for w in result.gate_state.warnings
            if "variance_loss" in w.lower()
        ]
        assert len(gate_state_warnings) > 0, (
            "variance_loss gate не сработал ни в warnings, ни в gate_state"
        )


class TestEnforceGatesUnit:
    """Unit tests for enforce_gates() function."""

    def _make_gate_state(self, gate_name, triggered=True, original=10.0, adjusted=5.0):
        """Helper to create GateState with one triggered gate."""
        from retouch.processing.core.gates import GateState, GateResult
        gs = GateState()
        gs.results.append(GateResult(
            gate_name=gate_name,
            step_name="test",
            triggered=triggered,
            original_value=original,
            adjusted_value=adjusted,
            reason=f"test {gate_name}",
        ))
        return gs

    def _make_ctx(self):
        """Helper to create minimal PipelineContext."""
        from retouch.processing.core.context import PipelineContext
        from PIL import Image
        img = Image.new('L', (100, 100), 128)
        return PipelineContext(img_gray=img)

    def _make_validated_plan(self, skin_delta=10.0):
        """Helper to create ValidatedPlan with skin_delta."""
        from retouch.processing.core.plan import PipelinePlan, ValidatedPlan
        plan = PipelinePlan(skin_delta=skin_delta)
        return ValidatedPlan(plan=plan)

    def test_clipped_pct_increases_compression(self):
        """clipped_pct gate → compression increased by 20%."""
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = self._make_gate_state("clipped_pct")
        ctx = self._make_ctx()
        vp = self._make_validated_plan()
        machine_cfg = {"rolloff_compression": 0.35}

        _, _, _, compression = enforce_gates(gs, machine_cfg, vp, ctx)

        assert compression == pytest.approx(0.42, abs=0.01)  # 0.35 * 1.2 = 0.42
        assert any("compression increased" in w for w in ctx.warnings)

    def test_p95_shift_halves_skin_delta(self):
        """p95_shift gate → skin_delta halved."""
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = self._make_gate_state("p95_shift")
        ctx = self._make_ctx()
        vp = self._make_validated_plan(skin_delta=10.0)
        machine_cfg = {}

        enforce_gates(gs, machine_cfg, vp, ctx)

        assert vp.plan.skin_delta == pytest.approx(5.0)
        assert any("skin_delta halved" in w for w in ctx.warnings)

    def test_shadow_crush_disables_floor_and_gamma(self):
        """shadow_crush gate → shadow_floor=0, gamma=1.0."""
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = self._make_gate_state("shadow_crush")
        ctx = self._make_ctx()
        vp = self._make_validated_plan()
        machine_cfg = {"shadow_floor": 5, "stone_gamma": 0.88}

        shadow_floor, stone_gamma, _, _ = enforce_gates(gs, machine_cfg, vp, ctx)

        assert shadow_floor == 0
        assert stone_gamma == 1.0
        assert any("shadow_floor" in w.lower() for w in ctx.warnings)
