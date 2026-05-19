"""Тесты для модуля gates.py — pre-check и post-check quality gates."""

import pytest

from retouch.processing.gates import (
    GateState,
    GateResult,
    pre_check_face_dark_small,
    pre_check_contour_inner_quality,
    pre_check_skin_delta_envelope,
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


class TestPreCheckSkinDeltaEnvelope:
    """Pre-check: skin_delta > envelope → clip."""

    def test_gate_skin_delta_exceeds_envelope(self):
        """skin_delta > envelope клипуется."""
        result = pre_check_skin_delta_envelope(
            skin_delta=50.0, max_delta=15.0
        )
        assert result.triggered is True
        assert result.adjusted_value == 15.0

    def test_gate_skin_delta_within_envelope(self):
        """skin_delta <= envelope не триггерит."""
        result = pre_check_skin_delta_envelope(
            skin_delta=10.0, max_delta=15.0
        )
        assert result.triggered is False

    def test_gate_skin_delta_negative(self):
        """Отрицательная delta тоже клипуется."""
        result = pre_check_skin_delta_envelope(
            skin_delta=-50.0, max_delta=15.0
        )
        assert result.triggered is True
        assert result.adjusted_value == -15.0


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
