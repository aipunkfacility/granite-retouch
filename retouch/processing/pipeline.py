"""Полный пайплайн обработки портрета для гравировки."""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from retouch.config import DEFAULTS, load_config, validate_config
from retouch.validation.image import (
    ValidationError,
    validate_image_input,
    validate_blue_chromakey,
    validate_result_black_ratio,
)
from retouch.processing.chromakey import remove_blue_background
from retouch.processing.analysis import analyze_input, ImageAnalytics
from retouch.processing.glow import apply_glow
from retouch.processing.levels import apply_levels
from retouch.processing.unsharp import apply_unsharp_mask
from retouch.processing.face_correction import check_face_brightness
from retouch.processing.shadow_noise import add_shadow_noise
from retouch.processing.face_region import detect_face_oval, generate_face_mask, generate_hair_mask
from retouch.processing.export import export_result
from retouch.processing.vignette import apply_vignette
from retouch.processing.mask_utils import clamp_masked
from retouch.processing.gamma import apply_stone_gamma_masked
from retouch.processing.zones import build_zone_masks, ZoneMasks
from retouch.processing.plan import (
    PipelinePlan,
    ValidatedPlan,
    SafetyEnvelope,
    validate_plan,
    PROFILE_STANDARD,
    PROFILE_PRESERVE,
    PROFILE_DIAGNOSTIC,
)
from retouch.processing.metrics import compute_zone_metrics, make_step_record, StepMetricsRecord
from retouch.processing.rolloff import soft_rolloff_masked
from retouch.processing.gates import (
    GateState,
    pre_check_face_dark_small,
    pre_check_contour_inner_quality,
    post_check_variance_loss,
    post_check_clipped_pct,
    post_check_p95_shift,
    post_check_shadow_crush,
)

# Pre-computed step order for post-check gates
_POST_CHECK_STEPS = ["glow", "levels", "face_correction", "unsharp", "postproc"]

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PipelineContext — внутренняя упаковка (B.1)
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """Внутренний контекст пайплайна — упаковка параметров.

    НЕ передаётся в функции обработки — они сохраняют текущие сигнатуры.
    Используется только внутри pipeline.py для уменьшения количества
    аргументов, пробрасываемых между шагами.

    Примечание: img_chromakey добавлено сверх плана (B.1) — оно нужно
    для передачи результата хромакея в PipelineResult без дополнительного
    возврата из _run_pipeline_steps(). Практичное дополнение, не ломает
    обратную совместимость.
    """
    img_gray: Image.Image
    img_chromakey: Image.Image | None = None
    subject_mask: Image.Image | None = None
    face_mask: Image.Image | None = None
    hair_mask: Image.Image | None = None
    hair_anomaly: bool = False
    hair_ratio: float = 0.0
    face_oval: dict[str, float] | None = None
    analytics: dict | None = None
    machine_type: str = "laser_standard"
    config: dict = field(default_factory=dict)
    machine_cfg: dict = field(default_factory=dict)
    stone_type: str = "granite"
    step_mm: float = 0.300
    face_brightness_before: float = 0.0
    face_brightness_after: float = 0.0
    correction_factor: float = 1.0
    warnings: list[str] = field(default_factory=list)
    debug_dir: str | None = None


# ---------------------------------------------------------------------------
# PipelineResult + consistency helpers
# ---------------------------------------------------------------------------


def _run_consistency_check(
    passed_oval: dict | None,
    result_oval: dict | None,
    warnings: list[str],
) -> None:
    """Проверить расхождение face_oval > 2% между переданным и результатом.

    Добавляет warning в список если расхождение > 0.02 по любому ключу.
    Используется в process_steps для consistency check preview → export.
    """
    if passed_oval is None or result_oval is None:
        return
    warn_keys = []
    for key in ("cx", "cy", "rx", "ry"):
        if key in passed_oval and key in result_oval:
            diff = abs(passed_oval[key] - result_oval[key])
            if diff > 0.02:
                warn_keys.append(f"{key}: {diff:.3f}")
    if warn_keys:
        msg = (
            f"consistency_mismatch: face_oval расхождение >2%: "
            f"{', '.join(warn_keys)}"
        )
        warnings.append(msg)
        logger.warning(msg)

@dataclass
class PipelineResult:
    """Результат пайплайна — все промежуточные этапы + диагностика."""

    # Промежуточные изображения (PIL.Image | None после release_intermediates)
    img_chromakey: Image.Image | None       # После хромакея (RGBA)
    img_gray: Image.Image | None            # После конвертации в L
    img_glow: Image.Image | None            # После Glow (L)
    img_leveled: Image.Image | None         # После Levels (L)
    img_face_corrected: Image.Image | None  # После face brightness correction (L)
    img_postproc: Image.Image | None        # После unsharp + shadow_noise + gamma (L)
    img_final: Image.Image                  # После виньетки (L) — всегда сохраняется
    arch_mask: Image.Image | None           # Маска виньетки (L)
    subject_mask: Image.Image | None        # Маска субъекта (L)
    face_mask: Image.Image | None           # Маска лица (L) — из face_region
    hair_mask: Image.Image | None           # Маска волос (L) — approximate

    # Диагностика
    glow_size: int
    glow_opacity: float
    face_brightness_before: float
    face_brightness_after: float
    face_correction_factor: float
    black_ratio: float
    blue_ratio: float
    width: int
    height: int
    analytics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # F.2: Метрики качества
    clipped_pixels_pct: float = 0.0
    shadow_crush_pct: float = 0.0
    tonal_range_output: float = 0.0
    quality_warnings: list[str] = field(default_factory=list)
    # AUDIT-3.1: Параметры овала лица для передачи preview → export
    face_oval: dict | None = None
    # Step metrics: метрики после каждого шага
    step_metrics: list[StepMetricsRecord] = field(default_factory=list)
    # Pipeline plan: план обработки
    plan: PipelinePlan | None = None
    # Validated plan: валидированный план
    validated_plan: ValidatedPlan | None = None
    # Zone masks: зональные маски
    zone_masks: ZoneMasks | None = None
    # Hair diagnostics
    hair_anomaly: bool = False
    hair_ratio: float = 0.0
    # Gate state: состояние quality gates
    gate_state: GateState | None = None

    def release_intermediates(self):
        """Освободить память от промежуточных изображений.

        После вызова доступ к img_chromakey, img_gray, img_glow, img_leveled,
        img_face_corrected, img_postproc, arch_mask, subject_mask, face_mask
        вернёт None. img_final остаётся доступным — он нужен для сохранения.
        """
        self.img_chromakey = None
        self.img_gray = None
        self.img_glow = None
        self.img_leveled = None
        self.img_face_corrected = None
        self.img_postproc = None
        self.arch_mask = None
        self.subject_mask = None
        self.face_mask = None

    def __enter__(self):
        """Контекстный менеджер: автоматическое освобождение при выходе."""
        return self

    def __exit__(self, *exc):
        """Освободить промежуточные при выходе из with-блока."""
        self.release_intermediates()

    # ─── Deprecated attribute access ──────────────────────────────────

    def __getattr__(self, name):
        """Deprecated attributes: img_sharpened → img_postproc."""
        import warnings as _w
        if name == "img_sharpened":
            _w.warn(
                "PipelineResult.img_sharpened is deprecated, use img_postproc instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.img_postproc
        raise AttributeError(f"'PipelineResult' object has no attribute {name!r}")

    def __setattr__(self, name, value):
        """Deprecated attributes: img_sharpened → img_postproc."""
        if name == "img_sharpened":
            import warnings as _w
            _w.warn(
                "PipelineResult.img_sharpened is deprecated, use img_postproc instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            super().__setattr__("img_postproc", value)
        else:
            super().__setattr__(name, value)




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

    # Конвертируем в grayscale если нужно
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

    # Клиппинг: пиксели >= white_ceiling
    clipped = np.sum(subject_pixels >= white_ceiling) / len(subject_pixels) * 100
    metrics["clipped_pixels_pct"] = float(clipped)

    # Shadow crush: пиксели <= shadow_floor
    crushed = np.sum(subject_pixels <= shadow_floor) / len(subject_pixels) * 100
    metrics["shadow_crush_pct"] = float(crushed)

    # Тональный диапазон (batch percentile)
    p10, p90 = np.percentile(subject_pixels, [10, 90])
    metrics["tonal_range_output"] = p90 - p10

    # Предупреждения
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


def process_steps(
    input_path: str | None = None,
    machine_type: str = "laser_standard",
    config: dict | None = None,
    glow_size_override: int | None = None,
    glow_opacity_override: float | None = None,
    face_oval: dict | None = None,
    no_validate: bool = False,
    keep_intermediates: bool = True,
    input_image: Image.Image | None = None,
    debug_dir: str | None = None,
    profile: str = PROFILE_STANDARD,
) -> PipelineResult:
    """Полный пайплайн с доступом к каждому шагу.

    Не сохраняет файлы. Не печатает в stdout.
    Возвращает PipelineResult со всеми промежуточными изображениями и диагностикой.

    Конвейер (A.3 — исправленный порядок):
        glow → levels → face_brightness → unsharp → shadow_noise → vignette

    При legacy_step_order=True в конфиге:
        glow → levels → unsharp → face_brightness → shadow_noise → vignette

    Args:
        input_path: путь к входному изображению (mutually exclusive с input_image)
        machine_type: тип станка
        config: конфигурация (None = загрузить из config.yaml)
        glow_size_override: ручное переопределение glow size
        glow_opacity_override: ручное переопределение glow opacity
        face_oval: ручное переопределение овала лица
        no_validate: отключить валидацию
        keep_intermediates: True = сохранять промежуточные (по умолчанию),
            False = освободить после сборки PipelineResult
        input_image: PIL.Image — входное изображение напрямую (без disk I/O).
            При передаче input_path игнорируется. Если оба None — ошибка.
            Изображение конвертируется в RGBA внутри функции.
        debug_dir: директория для отладочных масок
        profile: профиль обработки — preserve/standard/diagnostic

    Raises:
        FileNotFoundError: input_path не существует
        ValueError: невалидное изображение или конфиг
    """
    if config is None:
        config = load_config()

    # Валидация конфига
    validation_warnings = validate_config(config)

    # Загрузка изображения — из файла или из PIL напрямую
    if input_image is not None:
        img = input_image.convert("RGBA") if input_image.mode != "RGBA" else input_image.copy()
        if not no_validate:
            proc_cfg_v = config.get("processing", {})
            min_res = proc_cfg_v.get("min_resolution", 512)
            max_res = proc_cfg_v.get("max_resolution", None)
            w, h = img.size
            if w < min_res or h < min_res:
                raise ValidationError(
                    f"Разрешение {w}x{h} ниже минимума {min_res}x{min_res}. "
                    f"Для качественной гравировки нужно изображение большего размера."
                )
            if max_res and (w > max_res or h > max_res):
                raise ValidationError(
                    f"Разрешение {w}x{h} превышает максимум {max_res}x{max_res}. "
                    f"Слишком большое изображение может вызвать нехватку памяти (OOM)."
                )
    else:
        if input_path is None:
            raise ValueError("Нужен либо input_path, либо input_image")
        if not no_validate:
            validate_image_input(input_path, config)
        # AUDIT-2.2: контекстный менеджер — файловый дескриптор освобождается
        # даже при исключении между Image.open() и img.close()
        with Image.open(input_path) as img_file:
            img = img_file.convert("RGBA")

    width, height = img.size

    # Валидация хромакея
    proc_cfg = config.get("processing", {})
    threshold = proc_cfg.get("blue_threshold", 30)
    min_blue_ratio = proc_cfg.get("min_blue_ratio", 0.15)
    blue_ratio = 0.0
    if not no_validate:
        blue_ratio = validate_blue_chromakey(img, threshold=threshold, min_blue_ratio=min_blue_ratio)

    # 1. Хромакей
    fringe_radius = proc_cfg.get("fringe_radius", 3)
    mask_soft_sigma = proc_cfg.get("mask_soft_sigma", 1.5)
    contour_smooth_epsilon = proc_cfg.get("contour_smooth_epsilon", 0.002)
    img_chromakey, subject_mask = remove_blue_background(
        img, threshold=threshold, fringe_radius=fringe_radius,
        mask_soft_sigma=mask_soft_sigma,
        contour_smooth_epsilon=contour_smooth_epsilon,
    )
    # img — независимая копия (результат .convert()), закрытие не требуется

    # 2. Grayscale — RGB уже pre-multiplied по альфе в chromakey
    img_gray = img_chromakey.convert("L")

    # 2a. Детекция зоны лица (C.1: трёхуровневая стратегия)
    # FIX-ORD-007: делаем ДО analyze_input, чтобы метрики считались по лицу
    if face_oval is None:
        face_oval = detect_face_oval(img_gray, subject_mask=subject_mask)

    # 2b. Генерация маски лица из овала (C.2)
    face_mask = generate_face_mask(width, height, face_oval, subject_mask)

    # 2d. Генерация маски волос (Этап 0: hair_mask в diagnostics)
    hair_mask = generate_hair_mask(face_mask, subject_mask)
    hair_mask_arr = np.array(hair_mask) > 128
    hair_area = int(np.sum(hair_mask_arr))
    subject_area = int(np.sum(np.array(subject_mask) > 128))
    hair_ratio = hair_area / max(subject_area, 1)

    # Anomaly detection: hair-зона подозрительно велика или мала
    hair_anomaly = False
    hair_anomaly_reason = ""
    if subject_area > 0:
        if hair_ratio > 0.50:
            hair_anomaly = True
            hair_anomaly_reason = f"hair_ratio={hair_ratio:.2f} > 0.50 (подозрительно велика)"
        elif hair_ratio < 0.02 and hair_area > 0:
            hair_anomaly = True
            hair_anomaly_reason = f"hair_ratio={hair_ratio:.2f} < 0.02 (подозрительно мала)"

    if hair_anomaly:
        ctx.warnings.append(f"hair_mask anomaly: {hair_anomaly_reason}")
        logger.warning("Hair mask anomaly: %s", hair_anomaly_reason)

    # 2c. Преданализ — метрики по лицу (не по субъекту с одеждой)
    analytics = analyze_input(img_gray, np.array(subject_mask), np.array(face_mask))

    # B.1: Заполняем PipelineContext — внутренняя упаковка
    machine_cfg = proc_cfg.get(machine_type, {})
    ctx = PipelineContext(
        img_chromakey=img_chromakey,
        img_gray=img_gray,
        subject_mask=subject_mask,
        face_mask=face_mask,
        hair_mask=hair_mask,
        hair_anomaly=hair_anomaly,
        hair_ratio=hair_ratio,
        face_oval=face_oval,
        analytics=analytics,
        machine_type=machine_type,
        config=config,
        machine_cfg=machine_cfg,
        stone_type=config.get("stone", {}).get("type", "granite"),
        step_mm=machine_cfg.get("step_mm", config.get("machine", {}).get("step_mm", 0.300)),
        warnings=validation_warnings,
        debug_dir=debug_dir,
    )

    # Сохраняем маски для отладки
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        subject_mask.save(os.path.join(debug_dir, "subject_mask.png"))
        face_mask.save(os.path.join(debug_dir, "face_mask.png"))
        img_gray.save(os.path.join(debug_dir, "source_gray.png"))

    # B.1: Выполнение шагов через PipelineContext
    result = _run_pipeline_steps(
        ctx, proc_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        no_validate=no_validate,
        blue_ratio=blue_ratio,
        profile=profile,
    )

    # Consistency check: переданный face_oval vs результирующий
    _run_consistency_check(face_oval, result.face_oval, result.warnings)

    # Сохраняем промежуточные для отладки (до release_intermediates)
    if debug_dir:
        _steps = [
            ("step_00_chromakey.png", result.img_chromakey),
            ("step_01_glow.png", result.img_glow),
            ("step_02_levels.png", result.img_leveled),
            ("step_03_face_corrected.png", result.img_face_corrected),
        ]
        for fname, img in _steps:
            if img:
                img.save(os.path.join(debug_dir, fname))

    # Авто-освобождение промежуточных при keep_intermediates=False
    if not keep_intermediates:
        result.release_intermediates()

    return result


def _run_pipeline_steps(
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

    # PipelinePlan + ValidatedPlan
    plan = PipelinePlan.from_profile(profile, ctx.machine_cfg)
    envelope = SafetyEnvelope.from_config(ctx.config)
    validated = validate_plan(plan, profile, ctx.machine_cfg, envelope=envelope)

    # Gate state
    gate_state = GateState()

    # Step metrics
    step_metrics: list[StepMetricsRecord] = []
    _pipeline_start_ms = int(time.monotonic() * 1000)

    # ZoneMasks (если профиль не preserve)
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
            # Pre-check gates
            if zone_masks:
                face_dark_area = int(np.sum(zone_masks.face_dark))
                face_area = int(np.sum(zone_masks.face))
                gate = pre_check_face_dark_small(face_dark_area, face_area)
                gate_state.results.append(gate)

                contour_area = int(np.sum(zone_masks.contour_inner))
                subject_area = int(np.sum(zone_masks.subject))
                gate = pre_check_contour_inner_quality(contour_area, subject_area)
                gate_state.results.append(gate)
        except ValueError:
            # face_mask не построен — пропускаем зоны
            logger.warning("ZoneMasks не построены: face_mask unavailable")

    def _record_step(step_name: str, img: Image.Image | None):
        """Записать метрики шага в step_metrics + post-check gates."""
        nonlocal step_metrics, zone_masks
        if img is None or zone_masks is None:
            return
        arr = np.array(img, dtype=np.float32)
        masks_dict = {
            "face_skin": zone_masks.face_skin,
            "face_dark": zone_masks.face_dark,
            "hair": zone_masks.hair,
            "clothes": zone_masks.clothes,
            "highlights": zone_masks.highlights,
        }
        wc = ctx.machine_cfg.get("white_ceiling", 250)
        zm = compute_zone_metrics(arr, masks_dict, white_ceiling=wc)

        # Post-check gates
        warnings = []
        if len(step_metrics) > 0:
            prev = step_metrics[-1]
            fs_prev = prev.zone_metrics.get("face_skin")
            fs_curr = zm.get("face_skin")

            if fs_prev and fs_curr:
                # Variance loss
                gate = post_check_variance_loss(
                    fs_prev.variance, fs_curr.variance, step_name=step_name,
                )
                if gate.triggered:
                    gate_state.results.append(gate)
                    warnings.append(gate.reason)

                # P95 shift
                gate = post_check_p95_shift(
                    fs_prev.p95, fs_curr.p95, step_name=step_name,
                )
                if gate.triggered:
                    gate_state.results.append(gate)
                    warnings.append(gate.reason)

            # Clipped pct (always check)
            subj_clipped = zm.get("face_skin")
            if subj_clipped and subj_clipped.clipped_pct > 0:
                gate = post_check_clipped_pct(
                    subj_clipped.clipped_pct, step_name=step_name,
                )
                if gate.triggered:
                    gate_state.results.append(gate)
                    warnings.append(gate.reason)

        step_metrics.append(make_step_record(step_name, zm, warnings))

    # 3. Glow
    img_glow, glow_size, glow_opacity = apply_glow(
        ctx.img_gray, ctx.subject_mask, ctx.machine_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        analytics=ctx.analytics,
        machine_type=ctx.machine_type,
    )
    _record_step("glow", img_glow)

    # Определяем порядок шагов (A.3)
    legacy_order = proc_cfg.get("legacy_step_order", False)

    # 4. Levels
    face_skin_mask_for_levels = None
    if zone_masks is not None:
        face_skin_mask_for_levels = zone_masks.face_skin
    img_leveled = apply_levels(
        img_glow, analytics=ctx.analytics,
        machine_type=ctx.machine_type, subject_mask=ctx.subject_mask,
        machine_cfg=ctx.machine_cfg, face_skin_mask=face_skin_mask_for_levels,
    )
    _record_step("levels", img_leveled)

    if legacy_order:
        # СТАРЫЙ порядок (до A.3): unsharp ДО face_brightness
        img_temp = apply_unsharp_mask(
            img_leveled, subject_mask=ctx.subject_mask, analytics=ctx.analytics,
            threshold=ctx.machine_cfg.get("unsharp_threshold", 0),
            white_ceiling=ctx.machine_cfg.get("white_ceiling", None),
        )
        _record_step("unsharp", img_temp)
        img_face_corrected, face_before, face_after, correction_factor = _apply_face_brightness(
            img_temp, ctx.machine_cfg, ctx.subject_mask, glow_size, ctx.face_mask,
        )
        _record_step("face_correction", img_face_corrected)
        img_postproc = img_face_corrected  # В legacy-порядке unsharp уже применён
    else:
        # НОВЫЙ порядок (A.3): face_brightness ПЕРЕД unsharp
        img_face_corrected, face_before, face_after, correction_factor = _apply_face_brightness(
            img_leveled, ctx.machine_cfg, ctx.subject_mask, glow_size, ctx.face_mask,
        )
        _record_step("face_correction", img_face_corrected)
        img_postproc = apply_unsharp_mask(
            img_face_corrected, subject_mask=ctx.subject_mask, analytics=ctx.analytics,
            threshold=ctx.machine_cfg.get("unsharp_threshold", 0),
            white_ceiling=ctx.machine_cfg.get("white_ceiling", None),
        )
        _record_step("unsharp", img_postproc)

    # Gates enforcement перед postproc: если сработали gates, ослабляем параметры
    # Читаем конфиг ДО enforcement, чтобы gates могли ослабить параметры
    shadow_floor = ctx.machine_cfg.get("shadow_floor", 0)
    stone_gamma = ctx.machine_cfg.get("stone_gamma", None)
    white_ceiling = ctx.machine_cfg.get("white_ceiling", None)
    compression = ctx.machine_cfg.get("rolloff_compression", 0.35)
    triggered = {g.gate_name: g for g in gate_state.triggered_gates}
    if "variance_loss" in triggered and stone_gamma is not None and stone_gamma != 1.0:
        original_gamma = stone_gamma
        stone_gamma = 1.0 + (stone_gamma - 1.0) * 0.5
        logger.info(
            "Gates enforcement: variance_loss triggered, stone_gamma %.2f → %.2f",
            original_gamma, stone_gamma,
        )
        ctx.warnings.append(
            f"stone_gamma weakened: {original_gamma:.2f} → {stone_gamma:.2f} (variance_loss gate)"
        )

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

    if "p95_shift" in triggered:
        orig_delta = validated.plan.skin_delta
        validated.plan.skin_delta *= 0.5
        logger.info(
            "Gates enforcement: p95_shift triggered, skin_delta %.1f → %.1f",
            orig_delta, validated.plan.skin_delta,
        )
        ctx.warnings.append(
            f"skin_delta halved: {orig_delta:.1f} → {validated.plan.skin_delta:.1f} (p95_shift gate)"
        )

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
            f"shadow_floor и gamma отключены (shadow_crush gate)"
        )

    # Сохраняем результаты в контекст
    ctx.face_brightness_before = face_before
    ctx.face_brightness_after = face_after
    ctx.correction_factor = correction_factor

    # 5a. Shadow noise for impact (prevents needle stagnation on pure black)
    # ВАЖНО: shadow_noise ПЕРЕД shadow_floor! Шум добавляет текстуру,
    # затем shadow_floor гарантирует что ничего не уйдёт ниже пола.
    shadow_noise_min = ctx.machine_cfg.get("shadow_noise_min", 0)
    shadow_noise_max = ctx.machine_cfg.get("shadow_noise_max", 0)
    shadow_threshold = ctx.machine_cfg.get("shadow_noise_threshold", 30)
    if shadow_noise_max > 0 and ctx.machine_type == "impact":
        img_postproc = add_shadow_noise(
            img_postproc, ctx.subject_mask,
            noise_min=shadow_noise_min, noise_max=shadow_noise_max,
            shadow_threshold=shadow_threshold,
            shadow_floor=shadow_floor,
        )

    # A.2: Shadow floor — отдельный шаг (FIX #12: теперь для всех станков)
    # Предотвращает уход теней в 0 (игла застревает / «грязь» на камне).
    # После shadow_noise: гарантирует что шум не создал значения < floor.
    #
    # PERF: Объединяем shadow_floor + stone_gamma + white_ceiling в ОДИН numpy-проход.
    # Было 3× PIL→numpy→PIL (3 аллокации), стало 1× PIL→numpy→PIL.
    # stone_gamma, white_ceiling, compression прочитаны ДО enforcement (выше).

    needs_numpy = (
        (shadow_floor > 0) or
        (stone_gamma is not None and stone_gamma != 1.0) or
        (white_ceiling is not None)
    )

    if needs_numpy:
        arr = np.array(img_postproc, dtype=np.float32)
        mask_bool = np.array(ctx.subject_mask) > 128

        # Shadow floor
        # Этап 0: для laser — только в face_mask, не в hair/clothes
        # impact — по всей subject_mask (needle floor)
        if shadow_floor > 0:
            if ctx.machine_type == "impact":
                arr = clamp_masked(arr, ctx.subject_mask, vmin=shadow_floor, mask_bool=mask_bool)
                logger.info("Shadow floor applied: %d (impact, full subject)", shadow_floor)
            else:
                # laser_standard, laser_80w — только в зоне лица
                if ctx.face_mask is not None:
                    face_mask_bool = np.array(ctx.face_mask) > 128
                    floor_mask = mask_bool & face_mask_bool
                    if floor_mask.any():
                        arr[floor_mask] = np.maximum(arr[floor_mask], float(shadow_floor))
                        logger.info(
                            "Shadow floor applied: %d (laser, face_mask only, %d px)",
                            shadow_floor, int(floor_mask.sum()),
                        )
                    else:
                        logger.info("Shadow floor skipped: no face_mask overlap")
                else:
                    # Fallback: без face_mask не применяем floor для laser
                    logger.warning("Shadow floor skipped for laser: face_mask unavailable")

        # Stone gamma (SOP 5.1)
        if stone_gamma is not None and stone_gamma != 1.0:
            arr = apply_stone_gamma_masked(arr, mask_bool, gamma=stone_gamma)
            logger.info("Stone gamma applied: %.2f", stone_gamma)

        # White ceiling clamp ПОСЛЕ gamma — gamma < 1.0 осветляет
        # v6: soft_rolloff_masked вместо inline knee (единый helper)
        # v6.5: rolloff только по highlights-зоне (не весь subject)
        if white_ceiling is not None:
            knee = white_ceiling * 0.90
            if zone_masks is not None and zone_masks.highlights.any():
                rolloff_mask = zone_masks.highlights
                logger.info("White ceiling rolloff applied to highlights zone (%d px)", int(rolloff_mask.sum()))
            else:
                rolloff_mask = np.array(ctx.subject_mask, dtype=np.uint8)
            arr = soft_rolloff_masked(arr, rolloff_mask, knee, float(white_ceiling), compression)
            logger.info("White ceiling rolloff (post-gamma): %d, compression=%.2f", white_ceiling, compression)
            # Per-region face clamp удалён (v4—v5): создавал серое плато
            # по границе маски лица на всех трёх типах станка.
            # Защита от пересвета: levels→white_ceiling + face_correction→target_ceiling.

        img_postproc = Image.fromarray(arr.astype(np.uint8))

    _record_step("postproc", img_postproc)

    # 6. Vignette
    vign_cfg = ctx.config.get("vignette", {})
    if vign_cfg.get("enabled", True):
        img_final, arch_mask = apply_vignette(img_postproc, width, height, vign_cfg)
    else:
        img_final = img_postproc
        arch_mask = None

    # 7. Валидация результата
    black_ratio = 0.0
    if not no_validate:
        result_min_black = proc_cfg.get("result_min_black_ratio", 0.25)
        black_ratio = validate_result_black_ratio(img_final, min_black_ratio=result_min_black)

    # F.2: Метрики качества
    quality = _compute_quality_metrics(img_final, ctx.subject_mask, ctx.machine_cfg)

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


def _apply_face_brightness(img, machine_cfg, subject_mask, glow_size, face_mask=None):
    """Применить коррекцию яркости лица.

    Вынесено в отдельную функцию для поддержки разных порядков шагов (A.3).
    """
    # Support both old list format [min, max] and new separate keys
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
        face_mask_img=face_mask,  # C.3: маска лица из овала (приоритет над face_region_top)
        skin_threshold=skin_threshold,  # порог кожи: волосы < threshold, кожа >= threshold
    )


def process_preview(
    input_path: str,
    machine_type: str = "laser_standard",
    config: dict | None = None,
    max_size: int = 768,
    **kwargs,
) -> PipelineResult:
    """Предпросмотр — уменьшенная копия для Web UI.

    1. Загружает полное изображение ОДИН раз
    2. Уменьшает до max_size по длинной стороне (thumbnail), если нужно
    3. D.2: Минимальная высота >= 200 для широких кадров
    4. Передаёт уменьшенное PIL-изображение напрямую в process_steps() — БЕЗ disk I/O
    5. Возвращает PipelineResult (все картинки уменьшенные)

    Glow фиксируется на середине диапазона для стабильности preview (D.1).
    """
    if config is None:
        config = load_config()

    machine_cfg = config.get("processing", {}).get(machine_type, {})

    # D.1: Фиксируем glow для стабильного preview (deterministic)
    # Fallback из DEFAULTS по machine_type, а не хардкод laser_standard (40, 80, 30, 40)
    from retouch.config import DEFAULTS as _DEFAULTS
    _fb = _DEFAULTS["processing"].get(machine_type, _DEFAULTS["processing"]["laser_standard"])
    glow_min = machine_cfg.get("glow_size_min", _fb["glow_size_min"])
    glow_max = machine_cfg.get("glow_size_max", _fb["glow_size_max"])
    glow_mid = (glow_min + glow_max) // 2

    opacity_min = machine_cfg.get("glow_opacity_min", _fb["glow_opacity_min"])
    opacity_max = machine_cfg.get("glow_opacity_max", _fb["glow_opacity_max"])
    opacity_mid = (opacity_min + opacity_max) // 2

    # Открываем изображение ОДИН раз через контекстный менеджер —
    # гарантирует освобождение файлового дескриптора при любом исходе.
    with Image.open(input_path) as img:
        orig_w, orig_h = img.size
        needs_resize = max(orig_w, orig_h) > max_size

        if needs_resize:
            # FIX-4: Рассчитываем финальный размер ЗАРАНЕЕ — без повторного Image.open()
            # Стандартный thumbnail: уменьшаем по длинной стороне
            scale = max_size / max(orig_w, orig_h)
            target_w = int(orig_w * scale)
            target_h = int(orig_h * scale)

            # D.2: Минимальная высота >= 200 для широких кадров
            if target_h < 200:
                ratio = 200 / orig_h
                target_w = min(int(orig_w * ratio), max_size * 3)
                target_h = 200

            img.thumbnail((target_w, target_h), Image.LANCZOS)

        # Конвертируем в RGBA и передаём напрямую — БЕЗ disk I/O
        img_rgba = img.convert("RGBA") if img.mode != "RGBA" else img
        img_rgba.load()  # FIX-1: материализовать пиксели до закрытия файла (OSError на lazy .copy())

    return process_steps(
        input_image=img_rgba,
        machine_type=machine_type,
        config=config,
        glow_size_override=glow_mid,
        glow_opacity_override=opacity_mid,
        no_validate=True,  # Превью без строгой валидации
        **kwargs,
    )


def process_export(
    input_path: str,
    output_path: str,
    machine_type: str = "laser_standard",
    config: dict | None = None,
    fmt: str = "bmp",
    overwrite: bool = True,
    no_validate: bool = False,
    debug_dir: str | None = None,
    face_oval: dict | None = None,
    **kwargs,
) -> PipelineResult:
    """Полная обработка + сохранение BMP/PNG.

    Вызывает process_steps(), затем сохраняет результат через export_result().
    Формат BMP определяется по export_mode из per-machine конфига (v3):
    - Все машины по умолчанию: export_mode='8bit' → 8-bit grayscale BMP
    - При export_mode='1bit': 1-bit BMP с дизерингом (dither_method_1bit)
    - Явный fmt='bmp_8bit'/'bmp_1bit' перекрывает export_mode

    DPI в заголовке BMP вычисляется из per-machine step_mm: dpi = 25.4 / step_mm.
    Промежуточные изображения освобождаются для экономии памяти.

    Args:
        input_path: путь к входному изображению
        output_path: путь к выходному файлу
        machine_type: тип станка ('laser_standard', 'laser_80w', 'impact')
        config: конфигурация (None = загрузить из config.yaml)
        fmt: формат экспорта ('bmp', 'bmp_1bit', 'bmp_8bit', 'png')
        overwrite: D.7 — если False и файл существует, выбрасывает FileExistsError.
            CLI использует --overwrite флаг для управления.
        no_validate: AUDIT-2.1 — отключить валидацию (пробрасывается в process_steps)
    """
    # D.7: Проверка перезаписи — согласовано с CLI --overwrite
    output = Path(output_path)
    if output.exists():
        if not overwrite:
            raise FileExistsError(
                f"Выходной файл уже существует: {output_path}. "
                f"Используйте overwrite=True для перезаписи."
            )
        logger.warning("Output file already exists, overwriting: %s", output_path)

    result = process_steps(
        input_path=input_path,
        machine_type=machine_type,
        config=config,
        no_validate=no_validate,
        debug_dir=debug_dir,
        face_oval=face_oval,
        **kwargs,
    )

    # Сохранение BMP + PNG через export_result
    # Читаем export_mode, step_mm, dither_method_1bit из per-machine конфига
    proc_cfg = config.get("processing", {}) if config else {}
    machine_cfg = proc_cfg.get(machine_type, {})
    export_mode = machine_cfg.get("export_mode", "8bit")
    step_mm = machine_cfg.get("step_mm", config.get("machine", {}).get("step_mm", 0.300))
    dither_method_1bit = machine_cfg.get("dither_method_1bit",
                                          machine_cfg.get("dither_method", "jarvis"))
    dither_method = machine_cfg.get("dither_method", "none")  # deprecated fallback

    actual_path = export_result(
        result.img_final, output_path,
        machine_type=machine_type, fmt=fmt,
        export_mode=export_mode,
        step_mm=step_mm,
        dither_method=dither_method,  # deprecated fallback
        dither_method_1bit=dither_method_1bit,
        save_png_preview=True,  # CLI/WebUI ожидают PNG рядом с BMP
    )

    # F.3: BMP post-save валидация
    _validate_export(actual_path, machine_type, fmt)

    logger.info("Сохранено: %s (machine=%s, fmt=%s)", actual_path, machine_type, fmt)

    # Освобождаем промежуточные для экономии RAM
    result.release_intermediates()
    return result


def _validate_export(output_path: str, machine_type: str, fmt: str):
    """F.3: Пост-сохранная валидация BMP.

    Проверяет что файл можно открыть, mode и size соответствуют ожиданиям.
    fmt='bmp' использует export_mode из конфига: по умолчанию 8-bit для всех машин,
    но при export_mode='1bit' — 1-bit BMP с дизерингом.
    """
    try:
        with Image.open(output_path) as img:
            if fmt == "bmp_8bit":
                if img.mode not in ("L", "P"):
                    logger.warning(
                        "BMP 8-bit validation: expected mode L or P, got %s", img.mode
                    )
            elif fmt == "bmp":
                # fmt='bmp' — формат зависит от dither_method в конфиге станка
                if img.mode not in ("L", "P", "1"):
                    logger.warning(
                        "BMP validation: unexpected mode %s", img.mode
                    )
            elif fmt == "bmp_1bit":
                if img.mode != "1":
                    logger.warning(
                        "BMP 1-bit validation: expected mode 1, got %s", img.mode
                    )
    except Exception as e:
        raise RuntimeError(
            f"Пост-валидация не удалась: не удалось открыть {output_path}: {e}"
        ) from e


def process(input_path: str, output_path: str, machine_type: str = "laser_standard",
            glow_size_override: int | None = None, glow_opacity_override: float | None = None,
            config: dict | None = None, fmt: str = "bmp", overwrite: bool = True,
            no_validate: bool = False,
            face_oval: dict[str, float] | None = None,
            debug_dir: str | None = None) -> PipelineResult:
    """Обратная совместимая обёртка. CLI не ломается."""
    return process_export(
        input_path=input_path,
        output_path=output_path,
        machine_type=machine_type,
        config=config,
        fmt=fmt,
        overwrite=overwrite,
        no_validate=no_validate,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        face_oval=face_oval,  # AUDIT-3.1: проброс овала лица
        debug_dir=debug_dir,
    )
