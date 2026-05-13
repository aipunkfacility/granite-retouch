"""Полный пайплайн обработки портрета для гравировки."""

import logging
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
from retouch.processing.face_region import detect_face_oval, generate_face_mask
from retouch.processing.export import export_result
from retouch.processing.vignette import apply_vignette
from retouch.processing.mask_utils import clamp_masked
from retouch.processing.gamma import apply_stone_gamma_masked

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


# ---------------------------------------------------------------------------
# PipelineResult
# ---------------------------------------------------------------------------

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

    # 2. Grayscale
    img_gray = img_chromakey.convert("L")

    # 2a. Преданализ входного grayscale-изображения
    analytics = analyze_input(img_gray, np.array(subject_mask))

    # 2b. Детекция зоны лица (C.1: трёхуровневая стратегия)
    if face_oval is None:
        face_oval = detect_face_oval(img_gray, subject_mask=subject_mask)

    # 2c. Генерация маски лица из овала (C.2)
    face_mask = generate_face_mask(width, height, face_oval, subject_mask)

    # B.1: Заполняем PipelineContext — внутренняя упаковка
    machine_cfg = proc_cfg.get(machine_type, {})
    ctx = PipelineContext(
        img_chromakey=img_chromakey,
        img_gray=img_gray,
        subject_mask=subject_mask,
        face_mask=face_mask,
        face_oval=face_oval,
        analytics=analytics,
        machine_type=machine_type,
        config=config,
        machine_cfg=machine_cfg,
        stone_type=config.get("stone", {}).get("type", "granite"),
        step_mm=config.get("machine", {}).get("step_mm", 0.300),
        warnings=validation_warnings,
    )

    # B.1: Выполнение шагов через PipelineContext
    result = _run_pipeline_steps(
        ctx, proc_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        no_validate=no_validate,
        blue_ratio=blue_ratio,
    )

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
) -> PipelineResult:
    """B.1: Выполнение шагов пайплайна с использованием PipelineContext.

    Все параметры извлекаются из ctx, а не пробрасываются отдельно.
    Публичный API функций обработки НЕ меняется — ctx только упаковка.
    """
    width = ctx.img_gray.width
    height = ctx.img_gray.height

    # 3. Glow
    img_glow, glow_size, glow_opacity = apply_glow(
        ctx.img_gray, ctx.subject_mask, ctx.machine_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        analytics=ctx.analytics,
        machine_type=ctx.machine_type,
    )

    # Определяем порядок шагов (A.3)
    legacy_order = proc_cfg.get("legacy_step_order", False)

    # 4. Levels
    img_leveled = apply_levels(
        img_glow, analytics=ctx.analytics,
        machine_type=ctx.machine_type, subject_mask=ctx.subject_mask,
        machine_cfg=ctx.machine_cfg,
    )

    if legacy_order:
        # СТАРЫЙ порядок (до A.3): unsharp ДО face_brightness
        img_temp = apply_unsharp_mask(
            img_leveled, subject_mask=ctx.subject_mask, analytics=ctx.analytics,
            threshold=ctx.machine_cfg.get("unsharp_threshold", 0),
            white_ceiling=ctx.machine_cfg.get("white_ceiling", None),
        )
        img_face_corrected, face_before, face_after, correction_factor = _apply_face_brightness(
            img_temp, ctx.machine_cfg, ctx.subject_mask, glow_size, ctx.face_mask,
        )
        img_postproc = img_face_corrected  # В legacy-порядке unsharp уже применён
    else:
        # НОВЫЙ порядок (A.3): face_brightness ПЕРЕД unsharp
        img_face_corrected, face_before, face_after, correction_factor = _apply_face_brightness(
            img_leveled, ctx.machine_cfg, ctx.subject_mask, glow_size, ctx.face_mask,
        )
        img_postproc = apply_unsharp_mask(
            img_face_corrected, subject_mask=ctx.subject_mask, analytics=ctx.analytics,
            threshold=ctx.machine_cfg.get("unsharp_threshold", 0),
            white_ceiling=ctx.machine_cfg.get("white_ceiling", None),
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
    shadow_floor = ctx.machine_cfg.get("shadow_floor", 0)
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
    stone_gamma = ctx.machine_cfg.get("stone_gamma", None)
    white_ceiling = ctx.machine_cfg.get("white_ceiling", None)

    needs_numpy = (
        (shadow_floor > 0) or
        (stone_gamma is not None and stone_gamma != 1.0) or
        (white_ceiling is not None)
    )

    if needs_numpy:
        arr = np.array(img_postproc, dtype=np.float32)
        mask_bool = np.array(ctx.subject_mask) > 128

        # Shadow floor
        if shadow_floor > 0:
            arr = clamp_masked(arr, ctx.subject_mask, vmin=shadow_floor, mask_bool=mask_bool)
            logger.info("Shadow floor applied: %d (%s)", shadow_floor, ctx.machine_type)

        # Stone gamma (SOP 5.1)
        if stone_gamma is not None and stone_gamma != 1.0:
            arr = apply_stone_gamma_masked(arr, mask_bool, gamma=stone_gamma)
            logger.info("Stone gamma applied: %.2f", stone_gamma)

        # White ceiling clamp ПОСЛЕ gamma — gamma < 1.0 осветляет
        if white_ceiling is not None:
            arr = clamp_masked(arr, ctx.subject_mask, vmax=white_ceiling, mask_bool=mask_bool)
            logger.info("White ceiling clamp (post-gamma): %d", white_ceiling)

        img_postproc = Image.fromarray(arr.astype(np.uint8))

    # 6. Vignette
    vign_cfg = ctx.config.get("vignette", {})
    img_final, arch_mask = apply_vignette(img_postproc, width, height, vign_cfg)

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
    **kwargs,
) -> PipelineResult:
    """Полная обработка + сохранение BMP/PNG.

    Вызывает process_steps(), затем сохраняет результат.
    Формат BMP зависит от dither_method в конфиге станка:
    - laser_standard: dither_method='none' → 8-bit grayscale
    - laser_80w: dither_method='jarvis' → 1-bit BMP с Jarvis dithering
    - impact: dither_method='none' → 8-bit grayscale (256 уровней силы удара)
    Промежуточные изображения освобождаются для экономии памяти.

    Args:
        input_path: путь к входному изображению
        output_path: путь к выходному файлу
        machine_type: тип станка
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
        **kwargs,
    )

    # Сохранение BMP + PNG через export_result
    # Передаём dither_method из machine_cfg —
    # без этого export_result() не знает какой метод дизеринга использовать
    proc_cfg = config.get("processing", {}) if config else {}
    machine_cfg = proc_cfg.get(machine_type, {})
    dither_method = machine_cfg.get("dither_method", "none")

    actual_path = export_result(
        result.img_final, output_path,
        machine_type=machine_type, fmt=fmt,
        dither_method=dither_method,
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
    fmt='bmp' может давать как 8-bit (laser_standard), так и 1-bit (laser_80w/impact).
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
            face_oval: dict[str, float] | None = None) -> PipelineResult:
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
    )
