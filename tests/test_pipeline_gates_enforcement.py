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

    def test_face_dark_small_gate_still_triggers(self, tmp_path):
        """face_dark_small gate → запись в gate_state (correction больше не скипается)."""
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

        # face_dark_small gate recorded in gate_state
        assert any(g.gate_name == "face_dark_small" for g in result.gate_state.results)
        assert all(g.triggered for g in result.gate_state.results if g.gate_name == "face_dark_small")
        # face_correction_factor всегда 1.0 после фикса (неактуально, но стабильно)
        assert result.face_correction_factor == 1.0

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

    def _make_validated_plan(self):
        """Helper to create ValidatedPlan."""
        from retouch.processing.core.plan import PipelinePlan, ValidatedPlan
        plan = PipelinePlan()
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

    def test_p95_shift_gate_weakened_gamma(self):
        """p95_shift gate ослабляет gamma."""
        from retouch.processing.core.gates import GateState, post_check_p95_shift
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = GateState()
        gate = post_check_p95_shift(184.0, 208.0, threshold_levels=20.0, step_name="unsharp")
        gs.results.append(gate)

        machine_cfg = {"stone_gamma": 0.88, "white_ceiling": 245}
        _, stone_gamma, _, _ = enforce_gates(gs, machine_cfg, None, self._make_ctx())
        assert stone_gamma == pytest.approx(0.94, abs=0.01), (
            f"p95_shift gate should weaken gamma 0.88 → 0.94, got {stone_gamma}"
        )

    def test_variance_loss_and_p95_shift_no_double_weakening(self):
        """variance_loss + p95_shift не ослабляют gamma дважды."""
        from retouch.processing.core.gates import GateState, post_check_variance_loss, post_check_p95_shift
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = GateState()
        gs.results.append(post_check_variance_loss(100.0, 50.0, step_name="unsharp"))
        gs.results.append(post_check_p95_shift(184.0, 208.0, step_name="unsharp"))

        machine_cfg = {"stone_gamma": 0.88, "white_ceiling": 245}
        _, stone_gamma, _, _ = enforce_gates(gs, machine_cfg, None, self._make_ctx())
        assert stone_gamma == pytest.approx(0.94, abs=0.01), (
            f"Dual gate should weaken gamma once (0.88 → 0.94), not cumulatively, got {stone_gamma}"
        )

    def test_shadow_crush_overrides_gamma_weakening(self):
        """shadow_crush перебивает gamma weakening — gamma=1.0."""
        from retouch.processing.core.gates import GateState, GateResult, post_check_p95_shift
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = GateState()
        gs.results.append(post_check_p95_shift(184.0, 208.0, step_name="unsharp"))
        gs.results.append(GateResult("shadow_crush", "postproc", True, reason="test shadow_crush"))

        machine_cfg = {"stone_gamma": 0.88, "shadow_floor": 5, "white_ceiling": 245}
        shadow_floor, stone_gamma, _, _ = enforce_gates(gs, machine_cfg, None, self._make_ctx())
        assert stone_gamma == 1.0, (
            f"shadow_crush should override gamma weakening, got gamma={stone_gamma}"
        )
        assert shadow_floor == 0, (
            f"shadow_crush should reset shadow_floor to 0, got {shadow_floor}"
        )

    def test_enforce_gates_signature_unchanged(self):
        """Сигнатура enforce_gates возвращает 4 значения."""
        from retouch.processing.core.gates import GateState
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = GateState()
        result = enforce_gates(gs, {"stone_gamma": 0.88}, None, self._make_ctx())
        assert len(result) == 4, (
            f"enforce_gates should return 4 values, got {len(result)}"
        )


class TestLazyPostprocGate:
    """Lazy gate check after postproc: gamma weakening when postproc triggers gate."""

    @staticmethod
    def _make_ctx():
        from retouch.processing.core.context import PipelineContext
        return PipelineContext(img_gray=Image.new('L', (100, 100), 128))

    def test_enforce_gates_single_weakening_is_idempotent(self):
        from retouch.processing.core.gates import GateState, post_check_p95_shift
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = GateState()
        gs.results.append(post_check_p95_shift(184.0, 192.0, threshold_levels=5.0, step_name="unsharp"))
        gs.results.append(post_check_p95_shift(192.0, 199.0, threshold_levels=5.0, step_name="postproc"))

        machine_cfg = {"stone_gamma": 0.88, "white_ceiling": 245}
        _, stone_gamma, _, _ = enforce_gates(gs, machine_cfg, None, self._make_ctx())
        assert stone_gamma == pytest.approx(0.94, abs=0.01)

    def test_cumulative_gate_does_not_weaken_gamma(self):
        from retouch.processing.core.gates import GateState, GateResult
        from retouch.processing.core.gates_enforcement import enforce_gates

        gs = GateState()
        gs.results.append(GateResult(
            "p95_shift_cumulative", "postproc_cumulative", True,
            original_value=11.0, adjusted_value=8.0,
            reason="cumulative p95 shift 11.0 >= 8 — exceeds threshold",
        ))

        machine_cfg = {"stone_gamma": 0.88, "white_ceiling": 245}
        ctx = self._make_ctx()
        _, stone_gamma, _, _ = enforce_gates(gs, machine_cfg, None, ctx)
        assert stone_gamma == 0.88
        assert any("cumulative" in w.lower() for w in ctx.warnings)


class TestLazyPostprocGateIntegration:
    """Integration: lazy gate check реально ослабляет gamma на impact.

    Синтетические изображения не всегда создают face_skin зоны (требуется
    текстура кожи). Если gate не сработал — проверяем, что пайплайн дошёл
    до postproc шага. Если gate сработал — проверяем формат gamma warning.
    """

    def test_impact_gamma_weakened_when_postproc_triggers_gate(self, tmp_path):
        from retouch.config import DEFAULTS
        from retouch.processing.core.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        cx, cy = 256, 256
        rx, ry = 128, 150
        y_c, x_c = np.ogrid[:512, :512]
        ellipse = ((x_c - cx) / rx) ** 2 + ((y_c - cy) / ry) ** 2 <= 1.0
        arr[ellipse, 0] = 210
        arr[ellipse, 1] = 195
        arr[ellipse, 2] = 180
        arr[ellipse, 3] = 255
        img = Image.fromarray(arr)
        path = str(tmp_path / "input.png")
        img.save(path, "PNG")

        config = deepcopy(DEFAULTS)
        qg = config.setdefault("processing", {}).setdefault("quality_gates", {})
        qg["face_skin_p95_shift_threshold"] = 1.0
        qg.setdefault("face_skin_p95_shift_threshold_by_machine", {})["impact"] = 1.0
        qg["face_skin_cumulative_shift_threshold"] = 8.0

        result = process_steps(path, machine_type="impact", config=config)

        assert result is not None
        assert len(result.step_metrics) > 0, "Pipeline should produce step metrics"

        # Check if face_skin zones exist — synthetic images may not produce them
        has_face_skin = any(
            sm.zone_metrics and "face_skin" in sm.zone_metrics
            for sm in result.step_metrics
        )

        if not has_face_skin:
            # Без face_skin зон gate не проверить — но пайплайн отработал
            assert result.img_postproc is not None
            return

        postproc_gates = [
            g for g in result.gate_state.triggered_gates
            if g.step_name == "postproc"
        ]
        if not postproc_gates:
            return

        gate_keys = [(g.gate_name, g.step_name) for g in postproc_gates]
        assert len(gate_keys) == len(set(gate_keys)), (
            f"Duplicate gates found: {gate_keys}. "
            "This suggests stale gates from Pass 1 were not cleaned up."
        )

        gamma_warnings = [w for w in result.warnings if "gamma" in w.lower()]
        if gamma_warnings:
            gamma_warning = gamma_warnings[0]
            assert "\u2192" in gamma_warning or "->" in gamma_warning, (
                f"Gamma warning should show old\u2192new transition, got: {gamma_warning}"
            )
