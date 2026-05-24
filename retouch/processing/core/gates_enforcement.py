"""Gates enforcement — ослабление параметров при срабатывании gates."""

import logging

logger = logging.getLogger(__name__)


def enforce_gates(gate_state, machine_cfg, validated_plan, ctx):
    """Применить ослабление параметров по сработавшим gates.

    Args:
        gate_state: GateState — сработавшие gates
        machine_cfg: dict — параметры станка
        validated_plan: ValidatedPlan — план (может быть модифицирован)
        ctx: PipelineContext — контекст (для warnings)

    Returns:
        tuple: (shadow_floor, stone_gamma, white_ceiling, compression)
    """
    shadow_floor = machine_cfg.get("shadow_floor", 0)
    stone_gamma = machine_cfg.get("stone_gamma", None)
    white_ceiling = machine_cfg.get("white_ceiling", None)
    compression = machine_cfg.get("rolloff_compression", 0.35)

    triggered = {g.gate_name: g for g in gate_state.triggered_gates}

    # P1.3: shadow_crush — экстренный режим, проверяем ПЕРВЫМ.
    # Если тени раздавлены, отключаем все коррекции сразу.
    # Проверка первой избегает бессмысленного ослабления gamma,
    # которое перебивается shadow_crush.
    if "shadow_crush" in triggered:
        orig_floor = shadow_floor
        shadow_floor = 0
        orig_gamma = stone_gamma
        stone_gamma = 1.0
        logger.info(
            "Gates enforcement: shadow_crush triggered, shadow_floor %d → 0, gamma %.2f → 1.0",
            orig_floor, orig_gamma if orig_gamma else 1.0,
        )
        ctx.warnings.append(
            "shadow_floor и gamma отключены (shadow_crush gate)"
        )

    # P1.3: Gamma weakening — single-pass, NOT cumulative.
    # variance_loss и p95_shift оба ослабляют gamma, но ослабление
    # применяется ОДИН РАЗ — берётся максимальная причина.
    # Не применяется, если shadow_crush уже сбросил gamma=1.0.
    _gamma_weaken = False
    _weaken_reason = ""

    if "variance_loss" in triggered:
        _gamma_weaken = True
        _weaken_reason = "variance_loss"

    if "p95_shift" in triggered:
        _gamma_weaken = True
        if _weaken_reason:
            _weaken_reason = "variance_loss + p95_shift"
        else:
            _weaken_reason = "p95_shift"

    if _gamma_weaken and stone_gamma is not None and stone_gamma != 1.0:
        original_gamma = stone_gamma
        stone_gamma = 1.0 + (stone_gamma - 1.0) * 0.5
        logger.info(
            "Gates enforcement: %s triggered, stone_gamma %.2f → %.2f",
            _weaken_reason, original_gamma, stone_gamma,
        )
        ctx.warnings.append(
            f"stone_gamma weakened: {original_gamma:.2f} → {stone_gamma:.2f} ({_weaken_reason} gate)"
        )

    # Cumulative shift — diagnostic only: warning + log, NO gamma weakening
    if "p95_shift_cumulative" in triggered:
        if "p95_shift" not in triggered:
            logger.info(
                "Gates enforcement: p95_shift_cumulative triggered without per-step gate "
                "— logging only, no gamma weakening (each step within per-step threshold)"
            )
        else:
            logger.info(
                "Gates enforcement: p95_shift_cumulative + p95_shift both triggered "
                "— gamma already weakened by per-step gate"
            )
        ctx.warnings.append(
            "cumulative p95 shift exceeds threshold — check pipeline parameters"
        )

    # clipped_pct — не влияет на gamma
    if "clipped_pct" in triggered:
        orig_compression = compression
        compression = min(orig_compression * 1.2, 0.80)
        logger.info(
            "Gates enforcement: clipped_pct triggered, compression %.2f → %.2f",
            orig_compression, compression,
        )
        ctx.warnings.append(
            f"rolloff compression increased: {orig_compression:.2f} → {compression:.2f} (clipped_pct gate)"
        )

    return shadow_floor, stone_gamma, white_ceiling, compression
