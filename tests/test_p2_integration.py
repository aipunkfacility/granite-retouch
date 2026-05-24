"""Integration tests for P2: gate-trigger paradox + safety cap 0/1 mask fix."""

import pytest
from unittest.mock import MagicMock
from retouch.processing.core.gates import post_check_p95_shift, GateState
from retouch.processing.core.gates_enforcement import enforce_gates


def test_p2_regression_face_skin_brighter_after_p1():
    """P1 regression: face_skin brighter after P1 fix. P2 restores gamma weakening."""
    gate = post_check_p95_shift(190.0, 197.0, threshold_levels=5.0, step_name="unsharp")
    assert gate.triggered is True, "P2.1: gate must trigger at shift=7 with threshold=5"

    gate_state = GateState()
    gate_state.results.append(gate)

    machine_cfg = {"stone_gamma": 0.88, "shadow_floor": 2, "white_ceiling": 245, "rolloff_compression": 0.35}
    ctx = MagicMock()
    ctx.warnings = []

    shadow_floor, stone_gamma, white_ceiling, compression = enforce_gates(
        gate_state, machine_cfg, MagicMock(), ctx,
    )

    assert stone_gamma > 0.88, "P2.1: gamma must be weakened (raised towards 1.0) after p95_shift gate"
    assert stone_gamma == pytest.approx(0.94, abs=0.01), "gamma should be ~0.94"
