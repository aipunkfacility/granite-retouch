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
    pre_check_skin_delta_envelope, post_check_variance_loss, post_check_clipped_pct,
    post_check_p95_shift, post_check_shadow_crush,
)
from retouch.processing.core.gates_enforcement import enforce_gates
from retouch.processing.correction.glow import apply_glow
from retouch.processing.correction.levels import apply_levels
from retouch.processing.correction.face_correction import check_face_brightness
from retouch.processing.correction.unsharp import apply_unsharp_mask
from retouch.processing.correction.shadow_noise import add_shadow_noise
from retouch.processing.correction.postprocess import apply_postprocess
from retouch.processing.output.vignette import apply_vignette
from retouch.processing.analysis.zones import build_zone_masks, ZoneMasks
from retouch.processing.analysis.metrics import compute_zone_metrics, make_step_record, StepMetricsRecord, ZoneMetrics
from retouch.processing.correction.rolloff import soft_rolloff_masked

logger = logging.getLogger(__name__)


def _get_gate_thresholds(config: dict) -> dict:
    """Extract quality gate thresholds from config."""
    processing = config.get("processing", {})
    quality_gates = processing.get("quality_gates") or {}
    return {
        "variance_loss_threshold": quality_gates.get("variance_loss_threshold", 35.0),
        "clipped_pct_threshold": quality_gates.get("clipped_pct_threshold", 5.0),
        "p95_shift_threshold": quality_gates.get("p95_shift_threshold", 20.0),
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


def _apply_face_brightness(img, machine_cfg, subject_mask, glow_size, face_mask=None):
    """Применить коррекцию яркости лица.

    Вынесено в отдельную функцию для поддержки разных порядков шагов (A.3).
    """
    if "face_brightness_target" in machine_cfg:
        face_target = machine_cfg["face_brightness_target"]
    else:
        t_min = machine_cfg.get("face_brightness_target_min", 200)
        t_max = machine_cfg.get("face_brightness_target_max", 230)
        face_target = [t_min, t_max]

    face_region_top = machine_cfg.get("face_region_top", 0.45)
    highlight_start = machine_cfg.get("highlight_start", 200)
    white_ceiling = machine_cfg.get("white_ceiling", None)
    skin_threshold = machine_cfg.get("face_skin_threshold", 100)

    return check_face_brightness(
        img, face_target, subject_mask,
        glow_size=glow_size,
        face_region_top=face_region_top,
        highlight_start=highlight_start,
        white_ceiling=white_ceiling,
        face_mask_img=face_mask,
        skin_threshold=skin_threshold,
    )


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

    thresholds = _get_gate_thresholds(ctx.config)

    plan = PipelinePlan.from_profile(profile, ctx.machine_cfg)
    envelope = SafetyEnvelope.from_config(ctx.config)
    validated = validate_plan(plan, profile, ctx.machine_cfg, envelope=envelope)

    gate_state = GateState()

    step_metrics: list[StepMetricsRecord] = []
    _pipeline_start_ms = int(time.monotonic() * 1000)

    zone_masks: ZoneMasks | None = None
    if "levels" in validated.plan.active_steps or "face_correction" in validated.plan.active_steps:
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

                sd_gate = pre_check_skin_delta_envelope(
                    validated.plan.skin_delta, envelope.face_skin_max_delta,
                    step_name="plan_validation",
                )
                gate_state.results.append(sd_gate)
                if sd_gate.triggered:
                    validated.plan.skin_delta = sd_gate.adjusted_value
                    logger.info(
                        "Gate skin_delta_envelope: %.1f → %.1f",
                        sd_gate.original_value, sd_gate.adjusted_value,
                    )
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

                    gate = post_check_p95_shift(
                        fs_prev.p95, fs_curr.p95, step_name=step_name,
                        threshold_levels=thresholds["p95_shift_threshold"],
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

            step_metrics.append(make_step_record(step_name, zm, warnings))
        else:
            step_metrics.append(make_step_record(step_name, {}, []))

    img_glow, glow_size, glow_opacity = apply_glow(
        ctx.img_gray, ctx.subject_mask, ctx.machine_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        analytics=ctx.analytics,
        machine_type=ctx.machine_type,
    )
    _record_step("glow", img_glow)

    legacy_order = proc_cfg.get("legacy_step_order", False)

    img_leveled = img_glow
    img_face_corrected = img_glow
    img_postproc = img_glow
    face_before = 0.0
    face_after = 0.0
    correction_factor = 1.0

    if "levels" in validated.plan.active_steps:
        face_skin_mask_for_levels = None
        if zone_masks is not None:
            face_skin_mask_for_levels = zone_masks.face_skin
        img_leveled = apply_levels(
            img_glow, analytics=ctx.analytics,
            machine_type=ctx.machine_type, subject_mask=ctx.subject_mask,
            machine_cfg=ctx.machine_cfg, face_skin_mask=face_skin_mask_for_levels,
            zone_masks=zone_masks,
        )
        _record_step("levels", img_leveled)

    if legacy_order:
        if "unsharp" in validated.plan.active_steps:
            img_temp = apply_unsharp_mask(
                img_leveled, subject_mask=ctx.subject_mask, analytics=ctx.analytics,
                threshold=ctx.machine_cfg.get("unsharp_threshold", 0),
                white_ceiling=ctx.machine_cfg.get("white_ceiling", None),
            )
            _record_step("unsharp", img_temp)
        else:
            img_temp = img_leveled

        if "face_correction" in validated.plan.active_steps:
            face_dark_gates = [g for g in gate_state.results if g.gate_name == "face_dark_small"]
            if face_dark_gates and face_dark_gates[-1].triggered:
                logger.info("Gate face_dark_small triggered (legacy): face correction skipped")
                ctx.warnings.append("face_correction skipped: face_dark zone too small")
                img_face_corrected = img_temp
                face_before = 0.0
                face_after = 0.0
                correction_factor = 1.0
                _record_step("face_correction", img_face_corrected)
            else:
                img_face_corrected, face_before, face_after, correction_factor = _apply_face_brightness(
                    img_temp, ctx.machine_cfg, ctx.subject_mask, glow_size, ctx.face_mask,
                )
                _record_step("face_correction", img_face_corrected)
        else:
            img_face_corrected = img_temp
        img_postproc = img_face_corrected
    else:
        if "face_correction" in validated.plan.active_steps:
            face_dark_gates = [g for g in gate_state.results if g.gate_name == "face_dark_small"]
            if face_dark_gates and face_dark_gates[-1].triggered:
                logger.info("Gate face_dark_small triggered: face correction skipped")
                ctx.warnings.append("face_correction skipped: face_dark zone too small")
                img_face_corrected = img_leveled
                face_before = 0.0
                face_after = 0.0
                correction_factor = 1.0
                _record_step("face_correction", img_face_corrected)
            else:
                img_face_corrected, face_before, face_after, correction_factor = _apply_face_brightness(
                    img_leveled, ctx.machine_cfg, ctx.subject_mask, glow_size, ctx.face_mask,
                )
                _record_step("face_correction", img_face_corrected)
        else:
            img_face_corrected = img_leveled

        if "unsharp" in validated.plan.active_steps:
            img_postproc = apply_unsharp_mask(
                img_face_corrected, subject_mask=ctx.subject_mask, analytics=ctx.analytics,
                threshold=ctx.machine_cfg.get("unsharp_threshold", 0),
                white_ceiling=ctx.machine_cfg.get("white_ceiling", None),
            )
            _record_step("unsharp", img_postproc)
        else:
            img_postproc = img_face_corrected

    shadow_floor, stone_gamma, white_ceiling, compression = enforce_gates(
        gate_state, ctx.machine_cfg, validated, ctx,
    )

    ctx.face_brightness_before = face_before
    ctx.face_brightness_after = face_after
    ctx.correction_factor = correction_factor

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
        img_postproc = apply_postprocess(
            img_postproc,
            subject_mask=ctx.subject_mask,
            face_mask=ctx.face_mask,
            zone_masks=zone_masks,
            machine_type=ctx.machine_type,
            shadow_floor=shadow_floor,
            stone_gamma=stone_gamma,
            white_ceiling=white_ceiling,
            compression=compression,
        )
        _record_step("postproc", img_postproc)
    elif "highlight_rolloff" in validated.plan.active_steps:
        if zone_masks is not None and zone_masks.highlights is not None and zone_masks.highlights.any():
            arr = np.array(img_postproc, dtype=np.float32)
            rolloff_mask_arr = (zone_masks.highlights > 128).astype(np.uint8) * 255
            ceiling = float(ctx.machine_cfg.get("white_ceiling", 250))
            arr = soft_rolloff_masked(arr, rolloff_mask_arr, ceiling * 0.90, ceiling, compression)
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
        img_face_corrected=img_face_corrected,
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
