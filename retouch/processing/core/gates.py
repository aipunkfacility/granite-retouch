"""Quality gates — pre-check и post-check для пайплайна.

Pre-check: проверяет план ДО применения шага.
Post-check: проверяет результат ПОСЛЕ применения шага.

Все срабатывания пишутся в diagnostics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    gate_name: str
    step_name: str
    triggered: bool
    original_value: float | None = None
    adjusted_value: float | None = None
    reason: str = ""


@dataclass
class GateState:
    """Состояние всех gates."""
    results: list[GateResult] = field(default_factory=list)

    @property
    def triggered_gates(self) -> list[GateResult]:
        return [r for r in self.results if r.triggered]

    @property
    def warnings(self) -> list[str]:
        return [
            f"[{r.gate_name}] {r.reason}"
            for r in self.triggered_gates
        ]


# ---------------------------------------------------------------------------
# Pre-check gates
# ---------------------------------------------------------------------------

def pre_check_face_dark_small(
    face_dark_area: int,
    face_mask_area: int,
    threshold_pct: float = 5.0,
    step_name: str = "face_correction",
) -> GateResult:
    """Если face_dark < 5% от face_mask — пропустить коррекцию."""
    if face_mask_area == 0:
        return GateResult("face_dark_small", step_name, False)

    ratio = face_dark_area / face_mask_area * 100

    if ratio < threshold_pct:
        logger.info(
            "Gate face_dark_small: %.1f%% < %.1f%% — skip correction",
            ratio, threshold_pct,
        )
        return GateResult(
            "face_dark_small", step_name, True,
            original_value=ratio,
            adjusted_value=0.0,
            reason=f"face_dark {ratio:.1f}% < {threshold_pct}% — correction skipped",
        )

    return GateResult("face_dark_small", step_name, False)


def pre_check_contour_inner_quality(
    contour_inner_area: int,
    subject_area: int,
    threshold_pct: float = 30.0,
    step_name: str = "contour",
) -> GateResult:
    """Если contour_inner > 30% subject — fallback на morphological."""
    if subject_area == 0:
        return GateResult("contour_inner_quality", step_name, False)

    ratio = contour_inner_area / subject_area * 100

    if ratio > threshold_pct:
        logger.info(
            "Gate contour_inner_quality: %.1f%% > %.1f%% — fallback",
            ratio, threshold_pct,
        )
        return GateResult(
            "contour_inner_quality", step_name, True,
            original_value=ratio,
            adjusted_value=threshold_pct,
            reason=f"contour_inner {ratio:.1f}% > {threshold_pct}% — morphological fallback",
        )

    return GateResult("contour_inner_quality", step_name, False)


# ---------------------------------------------------------------------------
# Post-check gates
# ---------------------------------------------------------------------------

def post_check_variance_loss(
    variance_before: float,
    variance_after: float,
    threshold_pct: float = 35.0,
    step_name: str = "levels",
) -> GateResult:
    """Если variance loss > 35% — ослабить delta."""
    if variance_before == 0:
        return GateResult("variance_loss", step_name, False)

    loss_pct = (variance_before - variance_after) / variance_before * 100

    if loss_pct > threshold_pct:
        logger.info(
            "Gate variance_loss: %.1f%% > %.1f%% — weaken step",
            loss_pct, threshold_pct,
        )
        return GateResult(
            "variance_loss", step_name, True,
            original_value=loss_pct,
            adjusted_value=threshold_pct,
            reason=f"variance loss {loss_pct:.1f}% > {threshold_pct}% — delta weakened 50%",
        )

    return GateResult("variance_loss", step_name, False)


def post_check_clipped_pct(
    clipped_pct: float,
    threshold_pct: float = 5.0,
    step_name: str = "levels",
) -> GateResult:
    """Если clipped_pct > 5% — уменьшить rolloff/ceiling."""
    if clipped_pct <= threshold_pct:
        return GateResult("clipped_pct", step_name, False)

    logger.info(
        "Gate clipped_pct: %.1f%% > %.1f%% — reduce rolloff",
        clipped_pct, threshold_pct,
    )
    return GateResult(
        "clipped_pct", step_name, True,
        original_value=clipped_pct,
        adjusted_value=threshold_pct,
        reason=f"clipped {clipped_pct:.1f}% > {threshold_pct}% — rolloff reduced 20%",
    )


def post_check_p95_shift(
    p95_before: float,
    p95_after: float,
    threshold_levels: float = 20.0,
    step_name: str = "levels",
) -> GateResult:
    """Если p95 shift > 20 уровней — ослабить delta."""
    shift = abs(p95_after - p95_before)

    if shift <= threshold_levels:
        return GateResult("p95_shift", step_name, False)

    logger.info(
        "Gate p95_shift: %.1f > %.1f — weaken delta",
        shift, threshold_levels,
    )
    return GateResult(
        "p95_shift", step_name, True,
        original_value=shift,
        adjusted_value=threshold_levels,
        reason=f"p95 shift {shift:.1f} > {threshold_levels} — delta weakened 50%",
    )


def post_check_shadow_crush(
    crush_pct: float,
    threshold_pct: float = 10.0,
    step_name: str = "shadow_floor",
) -> GateResult:
    """Если shadow crush > 10% — не применять floor/gamma."""
    if crush_pct <= threshold_pct:
        return GateResult("shadow_crush", step_name, False)

    logger.info(
        "Gate shadow_crush: %.1f%% > %.1f%% — skip floor/gamma",
        crush_pct, threshold_pct,
    )
    return GateResult(
        "shadow_crush", step_name, True,
        original_value=crush_pct,
        adjusted_value=threshold_pct,
        reason=f"shadow crush {crush_pct:.1f}% > {threshold_pct}% — floor/gamma skipped",
    )
