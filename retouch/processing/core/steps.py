"""Функции выполнения шагов пайплайна — вынесены из pipeline.py."""

import logging
import os
import time

import numpy as np
from PIL import Image

from retouch.validation.image import validate_result_black_ratio
from retouch.processing.core.context import PipelineContext, PipelineResult
from retouch.processing.core.plan import (
    PipelinePlan, ValidatedPlan, SafetyEnvelope, validate_plan, PROFILE_STANDARD,
)
from retouch.processing.core.gates import (
    GateState, pre_check_face_dark_small, pre_check_contour_inner_quality,
    post_check_variance_loss, post_check_clipped_pct,
    post_check_p95_shift, post_check_shadow_crush,
)
from retouch.processing.core.gates_enforcement import enforce_gates
from retouch.processing.correction.glow import apply_glow
from retouch.processing.correction.face_brightness import face_brightness_correction
from retouch.processing.correction.unsharp import apply_unsharp_mask
from retouch.processing.correction.shadow_noise import add_shadow_noise
from retouch.processing.correction.postprocess import apply_postprocess
from retouch.processing.output.vignette import apply_vignette
from retouch.processing.analysis.zones import build_zone_masks, ZoneMasks
from retouch.processing.analysis.metrics import compute_zone_metrics, make_step_record, StepMetricsRecord, ZoneMetrics
from retouch.processing.correction.rolloff import soft_rolloff_masked, build_face_safe_rolloff_mask
from dataclasses import replace

logger = logging.getLogger(__name__)

# Safety margin: face_skin must stay at least this many levels BELOW the
# rolloff knee after gamma.  MUST match the constant in face_brightness.py.
FACE_SKIN_KNEE_MARGIN = 10


def _get_gate_thresholds(config: dict, machine_type: str | None = None) -> dict:
    """Extract quality gate thresholds from config."""
    processing = config.get("processing", {})
    quality_gates = processing.get("quality_gates") or {}

    # Per-machine-type face_skin threshold
    fs_threshold = quality_gates.get("face_skin_p95_shift_threshold", 3.0)
    if machine_type:
        machine_overrides = quality_gates.get("face_skin_p95_shift_threshold_by_machine", {})
        fs_threshold = machine_overrides.get(machine_type, fs_threshold)

    return {
        "variance_loss_threshold": quality_gates.get("variance_loss_threshold", 35.0),
        "clipped_pct_threshold": quality_gates.get("clipped_pct_threshold", 5.0),
        "p95_shift_threshold": quality_gates.get("p95_shift_threshold", 20.0),
        "face_skin_p95_shift_threshold": fs_threshold,
        "face_skin_cumulative_shift_threshold": quality_gates.get("face_skin_cumulative_shift_threshold", None),
        "shadow_crush_threshold": quality_gates.get("shadow_crush_threshold", 10.0),
        "face_dark_small_threshold": quality_gates.get("face_dark_small_threshold", 5.0),
        "contour_inner_quality_threshold": quality_gates.get("contour_inner_quality_threshold", 30.0),
    }


def _compute_quality_metrics(img_final, subject_mask, machine_cfg):
    """F.2: Вычислить метрики качества выходного изображения."""
    metrics = {
        "clipped_pixels_pct": 0.0,
        "shadow_crush_pct": 0.0,
        "tonal_range_output": 0.0,
        "quality_warnings": [],
    }

    if img_final is None or subject_mask is None:
        return metrics

    if img_final.mode == "RGB":
        img_arr = np.array(img_final.convert("L"), dtype=np.float32)
    else:
        img_arr = np.array(img_final, dtype=np.float32)

    mask_bool = np.array(subject_mask) > 128
    subject_pixels = img_arr[mask_bool]

    if len(subject_pixels) == 0:
        return metrics

    white_ceiling = machine_cfg.get("white_ceiling", 250)
    shadow_floor = machine_cfg.get("shadow_floor", 0)

    clipped = np.sum(subject_pixels >= white_ceiling) / len(subject_pixels) * 100
    metrics["clipped_pixels_pct"] = float(clipped)

    crushed = np.sum(subject_pixels <= shadow_floor) / len(subject_pixels) * 100
    metrics["shadow_crush_pct"] = float(crushed)

    p10, p90 = np.percentile(subject_pixels, [10, 90])
    metrics["tonal_range_output"] = p90 - p10

    quality_warnings = []
    if clipped > 5.0:
        quality_warnings.append(
            f"Высокий клиппинг: {clipped:.1f}% пикселей >= {white_ceiling}"
        )
    if crushed > 10.0:
        quality_warnings.append(
            f"Провал теней: {crushed:.1f}% пикселей <= {shadow_floor}"
        )
    if p90 - p10 < 30:
        quality_warnings.append(
            f"Узкий тональный диапазон: {p90 - p10:.0f} (p10={p10:.0f}, p90={p90:.0f})"
        )
    metrics["quality_warnings"] = quality_warnings

    return metrics


def run_pipeline_steps(
    ctx: PipelineContext,
    proc_cfg: dict,
    glow_size_override: int | None = None,
    glow_opacity_override: float | None = None,
    no_validate: bool = False,
    blue_ratio: float = 0.0,
    profile: str = PROFILE_STANDARD,
) -> PipelineResult:
    """B.1: Выполнение шагов пайплайна с использованием PipelineContext.

    Все параметры извлекаются из ctx, а не пробрасываются отдельно.
    Публичный API функций обработки НЕ меняется — ctx только упаковка.

    Интеграция новых модулей:
    - PipelinePlan: план обработки из профиля
    - ValidatedPlan: валидация параметров
    - ZoneMasks: зональные маски
    - Step metrics: метрики после каждого шага
    - Quality gates: pre/post-check
    - soft_rolloff_masked: единый ceiling helper
    """
    width = ctx.img_gray.width
    height = ctx.img_gray.height

    thresholds = _get_gate_thresholds(ctx.config, machine_type=ctx.machine_type)

    # face_oval_enabled: если False, убираем 'levels' из active_steps
    face_oval_enabled = ctx.config.get("processing", {}).get("face_oval_enabled", True)

    plan = PipelinePlan.from_profile(profile, ctx.machine_cfg)
    if not face_oval_enabled and "levels" in plan.active_steps:
        plan = replace(plan, active_steps=plan.active_steps - {"levels"})
        logger.info("face_oval_enabled=False: 'levels' убран из active_steps")

    envelope = SafetyEnvelope.from_config(ctx.config)
    validated = validate_plan(plan, profile, ctx.machine_cfg, envelope=envelope)

    gate_state = GateState()

    step_metrics: list[StepMetricsRecord] = []
    _pipeline_start_ms = int(time.monotonic() * 1000)

    zone_masks: ZoneMasks | None = None
    if "levels" in validated.plan.active_steps or "highlight_rolloff" in validated.plan.active_steps:
        try:
            zone_masks = build_zone_masks(
                subject_mask=ctx.subject_mask,
                face_mask=ctx.face_mask,
                img_gray=ctx.img_gray,
                skin_threshold=ctx.machine_cfg.get("face_skin_threshold", 100),
                highlight_threshold=ctx.machine_cfg.get("highlight_start", 200),
            )
            if zone_masks:
                face_dark_area = int(np.sum(zone_masks.face_dark))
                face_area = int(np.sum(zone_masks.face))
                gate = pre_check_face_dark_small(face_dark_area, face_area, threshold_pct=thresholds["face_dark_small_threshold"])
                gate_state.results.append(gate)

                contour_area = int(np.sum(zone_masks.contour_inner))
                subject_area = int(np.sum(zone_masks.subject))
                gate = pre_check_contour_inner_quality(contour_area, subject_area, threshold_pct=thresholds["contour_inner_quality_threshold"])
                gate_state.results.append(gate)
        except ValueError:
            logger.warning("ZoneMasks не построены: face_mask unavailable")

    def _record_step(step_name: str, img: Image.Image | None):
        """Записать метрики шага в step_metrics + post-check gates."""
        nonlocal step_metrics, zone_masks
        if img is None:
            return

        arr = np.array(img, dtype=np.float32)
        zm: dict[str, ZoneMetrics] = {}

        if zone_masks is not None:
            masks_dict = {
                "face_skin": zone_masks.face_skin,
                "face_dark": zone_masks.face_dark,
                "hair": zone_masks.hair,
                "clothes": zone_masks.clothes,
                "highlights": zone_masks.highlights,
            }
            wc = ctx.machine_cfg.get("white_ceiling", 250)
            zm = compute_zone_metrics(arr, masks_dict, white_ceiling=wc)

            warnings = []
            if len(step_metrics) > 0:
                prev = step_metrics[-1]
                fs_prev = prev.zone_metrics.get("face_skin")
                fs_curr = zm.get("face_skin")

                if fs_prev and fs_curr:
                    gate = post_check_variance_loss(
                        fs_prev.variance, fs_curr.variance, step_name=step_name,
                        threshold_pct=thresholds["variance_loss_threshold"],
                    )
                    if gate.triggered:
                        gate_state.results.append(gate)
                        warnings.append(gate.reason)

                    fs_threshold = thresholds.get("face_skin_p95_shift_threshold")
                    if fs_threshold is not None:
                        gate = post_check_p95_shift(
                            fs_prev.p95, fs_curr.p95, step_name=step_name,
                            threshold_levels=fs_threshold,
                        )
                        if gate.triggered:
                            gate_state.results.append(gate)
                            warnings.append(gate.reason)

                subj_clipped = zm.get("face_skin")
                if subj_clipped and subj_clipped.clipped_pct > 0:
                    gate = post_check_clipped_pct(
                        subj_clipped.clipped_pct, step_name=step_name,
                        threshold_pct=thresholds["clipped_pct_threshold"],
                    )
                    if gate.triggered:
                        gate_state.results.append(gate)
                        warnings.append(gate.reason)

            # Cumulative shift gate — от baseline ("input")
            if len(step_metrics) > 0 and zone_masks is not None:
                fs_curr_cum = zm.get("face_skin")
                if fs_curr_cum:
                    baseline_zm = step_metrics[0].zone_metrics.get("face_skin")
                    if baseline_zm:
                        _cumulative_shift = abs(fs_curr_cum.p95 - baseline_zm.p95)
                        cumulative_threshold = thresholds.get("face_skin_cumulative_shift_threshold")
                        if cumulative_threshold is not None and _cumulative_shift >= cumulative_threshold:
                            gate = post_check_p95_shift(
                                baseline_zm.p95, fs_curr_cum.p95,
                                step_name=f"{step_name}_cumulative",
                                threshold_levels=cumulative_threshold,
                                gate_name="p95_shift_cumulative",
                            )
                            if gate.triggered:
                                gate_state.results.append(gate)
                                warnings.append(gate.reason)

            step_metrics.append(make_step_record(step_name, zm, warnings))
        else:
            step_metrics.append(make_step_record(step_name, {}, []))

    _record_step("input", ctx.img_gray)

    img_glow, glow_size, glow_opacity = apply_glow(
        ctx.img_gray, ctx.subject_mask, ctx.machine_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        analytics=ctx.analytics,
        machine_type=ctx.machine_type,
    )
    _record_step("glow", img_glow)

    face_before = 0.0
    face_after = 0.0
    correction_factor = 1.0
    face_delta = 0.0

    if "levels" in validated.plan.active_steps:
        face_skin_mask_for_levels = None
        if zone_masks is not None:
            face_skin_mask_for_levels = zone_masks.get_bool("face_skin")
        img_leveled, face_before, face_after, correction_factor, face_delta = face_brightness_correction(
            img_glow,
            subject_mask=ctx.subject_mask,
            face_skin_mask=face_skin_mask_for_levels,
            machine_cfg=ctx.machine_cfg,
            analytics=ctx.analytics,
        )
        _record_step("levels", img_leveled)
    else:
        img_leveled = img_glow

    if "unsharp" in validated.plan.active_steps:
        _face_skin_for_unsharp = None
        if zone_masks is not None and zone_masks.face_skin is not None:
            _face_skin_for_unsharp = zone_masks.get_bool("face_skin")
        elif ctx.face_mask is not None and np.any(np.array(ctx.face_mask) > 128):
            logger.warning(
                "Unsharp: face_skin mask unavailable, face_mask fallback skipped "
                "(would clamp entire oval including brows/eyes). "
                "Overshoot protection applied without face_skin zone."
            )

        _overshoot_limit = max(1, ctx.machine_cfg.get("face_overshoot_limit", 8))

        img_postproc = apply_unsharp_mask(
            img_leveled, subject_mask=ctx.subject_mask, analytics=ctx.analytics,
            threshold=ctx.machine_cfg.get("unsharp_threshold", 0),
            white_ceiling=ctx.machine_cfg.get("white_ceiling", None),
            face_skin_mask=_face_skin_for_unsharp,
            face_overshoot_limit=_overshoot_limit,
        )
        _record_step("unsharp", img_postproc)
    else:
        img_postproc = img_leveled

    # P1.2: Gates enforcement — получаем ослабленные параметры
    shadow_floor, stone_gamma, white_ceiling, compression = enforce_gates(
        gate_state, ctx.machine_cfg, validated, ctx,
    )

    # Safety cap — использует ОСЛАБЛЕННУЮ gamma из gates (P1.2)
    # Applied AFTER unsharp (overshoot) and AFTER enforce_gates (weakened gamma),
    # BEFORE gamma+rolloff in postprocess.  Ensures face_skin stays below
    # (knee - FACE_SKIN_KNEE_MARGIN) after gamma, so rolloff never compresses
    # face_skin tonal variation into a gray plateau.
    if stone_gamma is not None and stone_gamma < 1.0:
        _fs_bool = None
        _mask_source = "none"
        if zone_masks is not None and zone_masks.face_skin is not None:
            _fs_bool = zone_masks.get_bool("face_skin")
            _mask_source = "zone_masks.face_skin"
        elif ctx.face_mask is not None and np.any(np.array(ctx.face_mask) > 128):
            # Fallback on face_mask is NOT applied — would clip face_dark (brows, eyes, shadows).
            # Better no cap than cap on entire oval. Log for diagnostics.
            logger.warning(
                "Safety cap: face_skin mask unavailable, face_mask fallback skipped "
                "(would clip face_dark: brows, eyes, shadows). "
                "This is expected if ZoneMasks are not built."
            )

        if _fs_bool is not None and _fs_bool.any():
            _ceiling = float(white_ceiling if white_ceiling is not None else ctx.machine_cfg.get("white_ceiling", 250))
            _knee = _ceiling * 0.90
            _safe_post_gamma = _knee - FACE_SKIN_KNEE_MARGIN
            _max_pre_gamma = np.power(_safe_post_gamma / 255.0, 1.0 / stone_gamma) * 255.0
            _soft_knee_start = _max_pre_gamma - 5.0

            _arr = np.array(img_postproc, dtype=np.float32)
            _above = _arr[_fs_bool] > _soft_knee_start
            if np.any(_above):
                _zone = _arr[_fs_bool].copy()
                _mask_above = _zone > _soft_knee_start
                _before_count = int(np.sum(_mask_above))
                _excess = _zone[_mask_above] - _soft_knee_start
                _range = _max_pre_gamma - _soft_knee_start
                _zone[_mask_above] = _soft_knee_start + _excess * (_range / (_excess + _range))
                _after_count = int(np.sum(_zone > _max_pre_gamma))
                _arr[_fs_bool] = _zone
                img_postproc = Image.fromarray(
                    np.clip(_arr, 0, 255).astype(np.uint8), mode='L',
                )
                logger.info(
                    "Safety cap (soft rolloff): %d face_skin pixels softened, "
                    "%d still above cap after rolloff "
                    "(knee=%.1f, margin=%d, gamma=%.2f, mask=%s)",
                    _before_count, _after_count, _knee,
                    FACE_SKIN_KNEE_MARGIN, stone_gamma, _mask_source,
                )
                _record_step("safety_cap", img_postproc)

    ctx.face_brightness_before = face_before
    ctx.face_brightness_after = face_after
    ctx.correction_factor = correction_factor
    ctx.face_brightness_delta = face_delta

    shadow_noise_min = ctx.machine_cfg.get("shadow_noise_min", 0)
    shadow_noise_max = ctx.machine_cfg.get("shadow_noise_max", 0)
    shadow_threshold = ctx.machine_cfg.get("shadow_noise_threshold", 30)
    if "shadow_noise" in validated.plan.active_steps and shadow_noise_max > 0 and ctx.machine_type == "impact":
        img_postproc = add_shadow_noise(
            img_postproc, ctx.subject_mask,
            noise_min=shadow_noise_min, noise_max=shadow_noise_max,
            shadow_threshold=shadow_threshold,
            shadow_floor=shadow_floor,
        )

    if set(validated.plan.active_steps) & {"shadow_floor", "stone_gamma", "white_ceiling"}:
        img_before_postproc = img_postproc

        # Pass 1: пробный postprocess для замера метрик
        img_postproc = apply_postprocess(
            img_before_postproc,
            subject_mask=ctx.subject_mask,
            face_mask=ctx.face_mask,
            zone_masks=zone_masks,
            machine_type=ctx.machine_type,
            shadow_floor=shadow_floor,
            stone_gamma=stone_gamma,
            white_ceiling=white_ceiling,
            compression=compression,
        )

        # Lazy gate check: проверяем ТОЛЬКО per-step gate вручную, БЕЗ _record_step.
        # Если per-step gate сработал — ослабляем gamma и повторяем postprocess.
        # Cumulative gate НЕ проверяем здесь — он будет вычислен в _record_step
        # на финальном изображении (после возможного Pass 2), и warning добавится
        # после _record_step. Это избегает: (1) дублей warnings и (2) устаревших
        # warnings от Pass 1, которые Pass 2 мог исправить.
        _needs_pass2 = False
        _postproc_step_gate_reasons = []

        if zone_masks is not None:
            _pp_arr = np.array(img_postproc, dtype=np.float32)
            _pp_masks = {
                "face_skin": zone_masks.face_skin,
                "face_dark": zone_masks.face_dark,
                "hair": zone_masks.hair,
                "clothes": zone_masks.clothes,
                "highlights": zone_masks.highlights,
            }
            _pp_wc = ctx.machine_cfg.get("white_ceiling", 250)
            _pp_zm = compute_zone_metrics(_pp_arr, _pp_masks, white_ceiling=_pp_wc)
            _fs_pp = _pp_zm.get("face_skin")
            _fs_prev = step_metrics[-1].zone_metrics.get("face_skin") if step_metrics else None

            if _fs_prev and _fs_pp:
                # Per-step gate only — cumulative проверяется ниже
                _pp_shift = abs(_fs_pp.p95 - _fs_prev.p95)
                _fs_threshold = thresholds.get("face_skin_p95_shift_threshold")
                if _fs_threshold is not None and _pp_shift >= _fs_threshold:
                    _needs_pass2 = True
                    _postproc_step_gate_reasons.append(
                        f"p95 shift {_pp_shift:.1f} >= {_fs_threshold} on postproc step"
                    )

        if _needs_pass2:
            _original_gamma = ctx.machine_cfg.get("stone_gamma", None)
            if _original_gamma is not None and _original_gamma != 1.0:
                _weakened_gamma = 1.0 + (_original_gamma - 1.0) * 0.5
                if abs(stone_gamma - _weakened_gamma) > 0.001:
                    logger.info(
                        "Postproc gate: stone_gamma %.2f \u2192 %.2f (gates: %s)",
                        stone_gamma, _weakened_gamma,
                        "; ".join(_postproc_step_gate_reasons),
                    )
                    ctx.warnings.append(
                        f"stone_gamma weakened after postproc: "
                        f"{_original_gamma:.2f} \u2192 {_weakened_gamma:.2f} "
                        f"(gate triggered during postproc step)"
                    )
                    stone_gamma = _weakened_gamma
                    # Pass 2: повторный postprocess с ослабленной gamma
                    img_postproc = apply_postprocess(
                        img_before_postproc,
                        subject_mask=ctx.subject_mask,
                        face_mask=ctx.face_mask,
                        zone_masks=zone_masks,
                        machine_type=ctx.machine_type,
                        shadow_floor=shadow_floor,
                        stone_gamma=stone_gamma,
                        white_ceiling=white_ceiling,
                        compression=compression,
                    )

        # Единый вызов _record_step на финальное изображение
        _record_step("postproc", img_postproc)

        # Post-_record_step cumulative warning:
        # _record_step добавляет GateResult в gate_state.results, но НЕ добавляет
        # warning в ctx.warnings. enforce_gates уже вызван раньше и не увидит
        # новые gates. Поэтому проверяем вручную — на основе финального изображения.
        _cum_gates = [
            g for g in gate_state.results
            if g.gate_name == "p95_shift_cumulative"
            and g.step_name == "postproc_cumulative"
            and g.triggered
        ]
        for _cg in _cum_gates:
            logger.info(
                "Cumulative gate: p95 shift %.1f >= %.1f — diagnostic only "
                "(does not trigger gamma weakening)",
                _cg.original_value, _cg.adjusted_value,
            )
            ctx.warnings.append(
                f"cumulative p95 shift {_cg.original_value:.1f} >= "
                f"{_cg.adjusted_value:.1f} — check pipeline parameters"
            )
    elif "highlight_rolloff" in validated.plan.active_steps:
        arr = np.array(img_postproc, dtype=np.float32)
        ceiling = float(ctx.machine_cfg.get("white_ceiling", 250))
        knee = ceiling * 0.90

        rolloff_mask = build_face_safe_rolloff_mask(
            ctx.subject_mask, ctx.face_mask, zone_masks,
            primary_zone="highlights_only",
            logger_prefix="highlight_rolloff",
        )
        if rolloff_mask is not None:
            arr = soft_rolloff_masked(arr, rolloff_mask, knee, ceiling, compression)

        img_postproc = Image.fromarray(arr.astype(np.uint8))
        _record_step("highlight_rolloff", img_postproc)

    vign_cfg = ctx.config.get("vignette", {})
    if vign_cfg.get("enabled", True):
        img_final, arch_mask = apply_vignette(img_postproc, width, height, vign_cfg)
    else:
        img_final = img_postproc
        arch_mask = None

    black_ratio = 0.0
    if not no_validate:
        result_min_black = proc_cfg.get("result_min_black_ratio", 0.25)
        black_ratio = validate_result_black_ratio(img_final, min_black_ratio=result_min_black)

    quality = _compute_quality_metrics(img_final, ctx.subject_mask, ctx.machine_cfg)

    sc_gate = post_check_shadow_crush(
        quality["shadow_crush_pct"],
        threshold_pct=thresholds["shadow_crush_threshold"],
    )
    if sc_gate.triggered:
        gate_state.results.append(sc_gate)

    logger.info(
        "Pipeline complete: %dx%d, glow=%dpx/%.0f%%, face=%.0f→%.0f",
        width, height, glow_size, glow_opacity * 100, face_before, face_after,
    )

    return PipelineResult(
        img_chromakey=ctx.img_chromakey,
        img_gray=ctx.img_gray,
        img_glow=img_glow,
        img_leveled=img_leveled,
        img_face_corrected=img_leveled,
        img_postproc=img_postproc,
        img_final=img_final,
        arch_mask=arch_mask,
        subject_mask=ctx.subject_mask,
        face_mask=ctx.face_mask,
        hair_mask=ctx.hair_mask,
        hair_anomaly=ctx.hair_anomaly,
        hair_ratio=ctx.hair_ratio,
        glow_size=glow_size,
        glow_opacity=glow_opacity,
        face_brightness_before=face_before,
        face_brightness_after=face_after,
        face_correction_factor=correction_factor,
        face_brightness_delta=ctx.face_brightness_delta,
        analytics=ctx.analytics,
        black_ratio=black_ratio,
        blue_ratio=blue_ratio,
        width=width,
        height=height,
        warnings=ctx.warnings,
        clipped_pixels_pct=quality["clipped_pixels_pct"],
        shadow_crush_pct=quality["shadow_crush_pct"],
        tonal_range_output=quality["tonal_range_output"],
        quality_warnings=quality["quality_warnings"],
        face_oval=ctx.face_oval,
        step_metrics=step_metrics,
        plan=validated.plan,
        validated_plan=validated,
        zone_masks=zone_masks,
        gate_state=gate_state,
    )
