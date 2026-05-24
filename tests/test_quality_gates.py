"""Тесты для модуля gates.py — pre-check и post-check quality gates."""

import pytest

from retouch.processing.core.gates import (
    GateState,
    GateResult,
    pre_check_face_dark_small,
    pre_check_contour_inner_quality,
    post_check_variance_loss,
    post_check_clipped_pct,
    post_check_p95_shift,
    post_check_shadow_crush,
)


class TestPreCheckFaceDarkSmall:
    """Pre-check: face_dark < 5% → skip correction."""

    def test_gate_face_dark_small_skip_correction(self):
        """face_dark < 5% пропускает коррекцию."""
        result = pre_check_face_dark_small(
            face_dark_area=10, face_mask_area=1000, threshold_pct=5.0
        )
        assert result.triggered is True
        assert "skip" in result.reason.lower()

    def test_gate_face_dark_small_not_triggered(self):
        """face_dark >= 5% не триггерит."""
        result = pre_check_face_dark_small(
            face_dark_area=100, face_mask_area=1000, threshold_pct=5.0
        )
        assert result.triggered is False

    def test_gate_face_dark_small_zero_face(self):
        """Нулевой face_mask_area не триггерит."""
        result = pre_check_face_dark_small(0, 0)
        assert result.triggered is False


class TestPreCheckContourInnerQuality:
    """Pre-check: contour_inner > 30% → fallback."""

    def test_gate_contour_inner_fallback(self):
        """contour_inner > 30% триггерит fallback."""
        result = pre_check_contour_inner_quality(
            contour_inner_area=400, subject_area=1000, threshold_pct=30.0
        )
        assert result.triggered is True
        assert "fallback" in result.reason.lower()

    def test_gate_contour_inner_not_triggered(self):
        """contour_inner <= 30% не триггерит."""
        result = pre_check_contour_inner_quality(
            contour_inner_area=200, subject_area=1000, threshold_pct=30.0
        )
        assert result.triggered is False


class TestPostCheckVarianceLoss:
    """Post-check: variance loss > 35% → weaken."""

    def test_gate_variance_loss_post_check(self):
        """variance loss > 35% ослабляет delta."""
        result = post_check_variance_loss(
            variance_before=100.0, variance_after=50.0, threshold_pct=35.0
        )
        assert result.triggered is True
        assert "weaken" in result.reason.lower()

    def test_gate_variance_loss_not_triggered(self):
        """variance loss <= 35% не триггерит."""
        result = post_check_variance_loss(
            variance_before=100.0, variance_after=80.0, threshold_pct=35.0
        )
        assert result.triggered is False


class TestPostCheckClippedPct:
    """Post-check: clipped_pct > 5% → reduce rolloff."""

    def test_gate_clipped_pct_post_check(self):
        """clipped_pct > 5% уменьшает rolloff."""
        result = post_check_clipped_pct(clipped_pct=10.0, threshold_pct=5.0)
        assert result.triggered is True
        assert "rolloff" in result.reason.lower()

    def test_gate_clipped_pct_not_triggered(self):
        """clipped_pct <= 5% не триггерит."""
        result = post_check_clipped_pct(clipped_pct=3.0, threshold_pct=5.0)
        assert result.triggered is False


class TestPostCheckP95Shift:
    """Post-check: p95 shift > 20 → weaken."""

    def test_gate_p95_shift_post_check(self):
        """p95 shift > 20 ослабляет delta."""
        result = post_check_p95_shift(
            p95_before=180.0, p95_after=210.0, threshold_levels=20.0
        )
        assert result.triggered is True

    def test_gate_p95_shift_not_triggered(self):
        """p95 shift <= 20 не триггерит."""
        result = post_check_p95_shift(
            p95_before=180.0, p95_after=195.0, threshold_levels=20.0
        )
        assert result.triggered is False


class TestPostCheckShadowCrush:
    """Post-check: shadow crush > 10% → skip floor/gamma."""

    def test_gate_shadow_crush_post_check(self):
        """shadow crush > 10% отключает floor/gamma."""
        result = post_check_shadow_crush(crush_pct=15.0, threshold_pct=10.0)
        assert result.triggered is True
        assert "skip" in result.reason.lower()

    def test_gate_shadow_crush_not_triggered(self):
        """shadow crush <= 10% не триггерит."""
        result = post_check_shadow_crush(crush_pct=5.0, threshold_pct=10.0)
        assert result.triggered is False


class TestGateState:
    """GateState агрегирует результаты."""

    def test_gates_write_diagnostics(self):
        """Gate срабатывания логируются в diagnostics."""
        state = GateState()
        state.results.append(GateResult(
            "variance_loss", "levels", True,
            original_value=40.0, adjusted_value=35.0,
            reason="variance loss 40% > 35%",
        ))
        assert len(state.triggered_gates) == 1
        assert len(state.warnings) == 1
        assert "variance_loss" in state.warnings[0]


class TestGateEnforcement:
    """Quality gates enforcement ослабляет параметры."""

    def test_p95_shift_enforcement_weakens_delta(self):
        """p95_shift > 20 ослабляет delta на 50%."""
        from retouch.processing.core.gates import post_check_p95_shift

        gate = post_check_p95_shift(180.0, 210.0, threshold_levels=20.0)
        assert gate.triggered
        assert "weaken" in gate.reason.lower()

    def test_shadow_crush_enforcement_skips_floor(self):
        """shadow_crush > 10% отключает floor/gamma."""
        from retouch.processing.core.gates import post_check_shadow_crush

        gate = post_check_shadow_crush(15.0, threshold_pct=10.0)
        assert gate.triggered
        assert "skip" in gate.reason.lower()

    def test_multiple_gates_enforcement_chain(self):
        """Несколько gates срабатывают последовательно."""
        from retouch.processing.core.gates import GateState, GateResult

        state = GateState()
        state.results.append(GateResult("variance_loss", "levels", True, reason="variance loss 40%"))
        state.results.append(GateResult("p95_shift", "levels", True, reason="p95 shift 25"))
        assert len(state.triggered_gates) == 2


class TestQualityGatesFromConfig:
    """Quality gate thresholds are configurable from config.yaml."""

    def test_gate_thresholds_from_config_yaml(self):
        """Gate thresholds are readable from config.yaml quality_gates section."""
        from retouch.config import load_config
        config = load_config()
        processing = config.get("processing", {})
        quality_gates = processing.get("quality_gates", {})

        assert "variance_loss_threshold" in quality_gates
        assert "clipped_pct_threshold" in quality_gates
        assert "p95_shift_threshold" in quality_gates
        assert "shadow_crush_threshold" in quality_gates
        assert "face_dark_small_threshold" in quality_gates
        assert "contour_inner_quality_threshold" in quality_gates

        # Verify defaults match current hardcoded values
        assert quality_gates["variance_loss_threshold"] == 35.0
        assert quality_gates["clipped_pct_threshold"] == 5.0
        assert quality_gates["p95_shift_threshold"] == 20.0
        assert quality_gates["shadow_crush_threshold"] == 10.0
        assert quality_gates["face_dark_small_threshold"] == 5.0
        assert quality_gates["contour_inner_quality_threshold"] == 30.0

    def test_get_gate_thresholds_returns_all_keys(self):
        """_get_gate_thresholds returns all 8 threshold keys."""
        from retouch.processing.core.steps import _get_gate_thresholds
        thresholds = _get_gate_thresholds({"processing": {"quality_gates": {}}})
        assert len(thresholds) == 8
        assert all(k in thresholds for k in [
            "variance_loss_threshold", "clipped_pct_threshold", "p95_shift_threshold",
            "face_skin_p95_shift_threshold", "face_skin_cumulative_shift_threshold",
            "shadow_crush_threshold", "face_dark_small_threshold",
            "contour_inner_quality_threshold",
        ])

    def test_get_gate_thresholds_uses_custom_values(self):
        """_get_gate_thresholds uses custom values from config, not defaults."""
        from retouch.processing.core.steps import _get_gate_thresholds
        config = {
            "processing": {
                "quality_gates": {
                    "variance_loss_threshold": 50.0,
                    "clipped_pct_threshold": 10.0,
                }
            }
        }
        thresholds = _get_gate_thresholds(config)
        assert thresholds["variance_loss_threshold"] == 50.0
        assert thresholds["clipped_pct_threshold"] == 10.0
        # Others should be defaults
        assert thresholds["p95_shift_threshold"] == 20.0

    def test_get_gate_thresholds_missing_quality_gates_section(self):
        """_get_gate_thresholds returns defaults when quality_gates section is absent."""
        from retouch.processing.core.steps import _get_gate_thresholds
        thresholds = _get_gate_thresholds({"processing": {}})
        assert thresholds["variance_loss_threshold"] == 35.0
        assert thresholds["clipped_pct_threshold"] == 5.0

    def test_get_gate_thresholds_missing_processing_section(self):
        """_get_gate_thresholds returns defaults when processing section is absent."""
        from retouch.processing.core.steps import _get_gate_thresholds
        thresholds = _get_gate_thresholds({})
        assert thresholds["variance_loss_threshold"] == 35.0
        assert thresholds["shadow_crush_threshold"] == 10.0

    def test_get_gate_thresholds_null_quality_gates(self):
        """_get_gate_thresholds handles quality_gates: null gracefully."""
        from retouch.processing.core.steps import _get_gate_thresholds
        config = {"processing": {"quality_gates": None}}
        thresholds = _get_gate_thresholds(config)
        assert len(thresholds) == 8
        assert thresholds["variance_loss_threshold"] == 35.0
        assert thresholds["face_skin_p95_shift_threshold"] == 3.0


def test_get_gate_thresholds_from_defaults():
    """DEFAULTS quality_gates: ключи существуют, cumulative=None (disabled by default)."""
    from retouch.config import DEFAULTS
    from retouch.processing.core.steps import _get_gate_thresholds

    thresholds = _get_gate_thresholds(DEFAULTS, machine_type=None)
    assert thresholds["face_skin_p95_shift_threshold"] == 3.0
    assert thresholds["face_skin_cumulative_shift_threshold"] is None
    assert thresholds["p95_shift_threshold"] == 20.0

    thresholds_impact = _get_gate_thresholds(DEFAULTS, machine_type="impact")
    assert thresholds_impact["face_skin_p95_shift_threshold"] == 5.0

    thresholds_80w = _get_gate_thresholds(DEFAULTS, machine_type="laser_80w")
    assert thresholds_80w["face_skin_p95_shift_threshold"] is None


class TestP21FaceSkinP95ShiftGate:
    """P2.1: face_skin zone uses lowered p95 shift threshold (5 instead of 20)."""

    def test_face_skin_p95_shift_lower_threshold(self):
        """face_skin zone uses lowered threshold 5 instead of 20."""
        gate = post_check_p95_shift(190.0, 198.0, threshold_levels=5.0)
        assert gate.triggered is True
        assert gate.gate_name == "p95_shift"

    def test_face_skin_p95_shift_at_threshold(self):
        """shift=5.0 == threshold 5.0 → gate triggers (>= semantics)."""
        gate = post_check_p95_shift(190.0, 195.0, threshold_levels=5.0)
        assert gate.triggered is True

    def test_face_skin_p95_shift_just_above_threshold(self):
        """shift=5.1 > threshold 5.0 → gate triggers."""
        gate = post_check_p95_shift(190.0, 195.1, threshold_levels=5.0)
        assert gate.triggered is True

    def test_face_skin_p95_shift_below_threshold(self):
        """shift=4 does not trigger lowered threshold 5."""
        gate = post_check_p95_shift(190.0, 194.0, threshold_levels=5.0)
        assert gate.triggered is False

    def test_general_zone_uses_default_threshold(self):
        """Non-face_skin zones use threshold 20."""
        gate_general = post_check_p95_shift(190.0, 205.0, threshold_levels=20.0)
        assert gate_general.triggered is False

        gate_fs = post_check_p95_shift(190.0, 205.0, threshold_levels=5.0)
        assert gate_fs.triggered is True

    def test_shift_7_triggers_threshold_5(self):
        """p95 shift=7 > 5 → gate triggers (typical case after amplitude cap ±8)."""
        gate = post_check_p95_shift(190.0, 197.0, threshold_levels=5.0)
        assert gate.triggered is True


# --- >= semantics ---
def test_p95_shift_at_boundary_triggers():
    """shift == threshold → triggers (>= semantics)."""
    gate = post_check_p95_shift(200.0, 203.0, threshold_levels=3.0)
    assert gate.triggered is True


def test_variance_loss_at_boundary_triggers():
    gate = post_check_variance_loss(100.0, 65.0, threshold_pct=35.0)
    assert gate.triggered is True


def test_clipped_pct_at_boundary_triggers():
    gate = post_check_clipped_pct(5.0, threshold_pct=5.0)
    assert gate.triggered is True


def test_shadow_crush_at_boundary_triggers():
    gate = post_check_shadow_crush(10.0, threshold_pct=10.0)
    assert gate.triggered is True


# --- gate_name parameter ---
def test_p95_shift_default_gate_name():
    gate = post_check_p95_shift(200.0, 208.0, threshold_levels=3.0)
    assert gate.gate_name == "p95_shift"


def test_p95_shift_cumulative_gate_name():
    gate = post_check_p95_shift(
        198.0, 208.0, threshold_levels=8.0,
        step_name="postproc_cumulative",
        gate_name="p95_shift_cumulative",
    )
    assert gate.gate_name == "p95_shift_cumulative"
    assert gate.triggered is True
    assert "exceeds threshold" in gate.reason
    assert "weakened" not in gate.reason


def test_p95_shift_per_step_reason_mentions_weakening():
    """Per-step gate reason still says 'weakened' — it actually weakens gamma."""
    gate = post_check_p95_shift(190.0, 197.0, threshold_levels=5.0)
    assert gate.triggered is True
    assert "weakened" in gate.reason


# --- per-machine-type lookup ---
def test_per_machine_type_threshold_lookup():
    from retouch.processing.core.steps import _get_gate_thresholds
    config = {
        "processing": {
            "quality_gates": {
                "face_skin_p95_shift_threshold": 3.0,
                "face_skin_p95_shift_threshold_by_machine": {
                    "laser_standard": 3.0,
                    "laser_80w": None,
                    "impact": 5.0,
                },
            }
        }
    }
    assert _get_gate_thresholds(config, "laser_standard")["face_skin_p95_shift_threshold"] == 3.0
    assert _get_gate_thresholds(config, "laser_80w")["face_skin_p95_shift_threshold"] is None
    assert _get_gate_thresholds(config, "impact")["face_skin_p95_shift_threshold"] == 5.0
    assert _get_gate_thresholds(config, "unknown")["face_skin_p95_shift_threshold"] == 3.0
    assert _get_gate_thresholds(config, None)["face_skin_p95_shift_threshold"] == 3.0


# --- None threshold guard ---
def test_none_threshold_guard():
    """When threshold is None, gate must NOT be called (would TypeError)."""
    thresholds = {"face_skin_p95_shift_threshold": None}
    fs_threshold = thresholds.get("face_skin_p95_shift_threshold")
    assert fs_threshold is None
    # post_check_p95_shift(threshold_levels=None) → TypeError
    # Guard ensures gate is NOT called when fs_threshold is None


class TestCumulativeGateEnforcement:
    """Cumulative gate does NOT weaken gamma — diagnostic only."""

    def test_cumulative_gate_no_gamma_weakening(self):
        from retouch.processing.core.gates import GateState, GateResult
        from retouch.processing.core.gates_enforcement import enforce_gates
        from retouch.processing.core.context import PipelineContext
        from PIL import Image

        gs = GateState()
        gs.results.append(GateResult(
            "p95_shift_cumulative", "postproc_cumulative", True,
            original_value=11.0, adjusted_value=8.0,
            reason="cumulative p95 shift 11.0 >= 8 — exceeds threshold",
        ))

        ctx = PipelineContext(img_gray=Image.new('L', (100, 100), 128))
        machine_cfg = {"stone_gamma": 0.88, "white_ceiling": 245}

        _, stone_gamma, _, _ = enforce_gates(gs, machine_cfg, None, ctx)
        assert stone_gamma == 0.88
        assert any("cumulative" in w.lower() for w in ctx.warnings)
