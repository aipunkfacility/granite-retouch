"""Полный пайплайн обработки портрета для гравировки."""

import logging
import tempfile
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
from retouch.processing.levels import (
    apply_levels, apply_unsharp_mask, check_face_brightness, add_shadow_noise,
)
from retouch.processing.face_region import detect_face_oval, generate_face_mask
from retouch.processing.export import export_result
from retouch.processing.vignette import apply_vignette
from retouch.processing.mask_utils import clamp_masked
from retouch.processing.gamma import apply_stone_gamma_masked

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

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
    face_oval: dict | None = None
    analytics: dict | None = None
    machine_type: str = "laser_standard"
    config: dict = field(default_factory=dict)
    machine_cfg: dict = field(default_factory=dict)
    stone_type: str = "granite"
    step_mm: float = 0.300
    face_brightness_before: float = 0.0
    face_brightness_after: float = 0.0
    correction_factor: float = 1.0
    warnings: list = field(default_factory=list)


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
    img_sharpened: Image.Image | None       # После unsharp (L)
    img_final: Image.Image                  # После виньетки (RGB) — всегда сохраняется
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

    def release_intermediates(self):
        """Освободить память от промежуточных изображений.

        После вызова доступ к img_chromakey, img_gray, img_glow, img_leveled,
        img_face_corrected, img_sharpened, arch_mask, subject_mask, face_mask
        вернёт None. img_final остаётся доступным — он нужен для сохранения.
        """
        self.img_chromakey = None
        self.img_gray = None
        self.img_glow = None
        self.img_leveled = None
        self.img_face_corrected = None
        self.img_sharpened = None
        self.arch_mask = None
        self.subject_mask = None
        self.face_mask = None


def _compute_quality_metrics(img_final, subject_mask, machine_cfg):
    """F.2: Вычислить метрики качества выходного изображения."""
    metrics = {
        "clipped_pixels_pct": 0.0,
        "shadow_crush_pct": 0.0,
        "tonal_range_output": 0.0,
        "quality_warnings": [],
    }

    if not HAS_NUMPY or img_final is None or subject_mask is None:
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

    # Тональный диапазон
    p10 = float(np.percentile(subject_pixels, 10))
    p90 = float(np.percentile(subject_pixels, 90))
    metrics["tonal_range_output"] = p90 - p10

    # Предупреждения
    warnings = []
    if clipped > 5.0:
        warnings.append(
            f"Высокий клиппинг: {clipped:.1f}% пикселей >= {white_ceiling}"
        )
    if crushed > 10.0:
        warnings.append(
            f"Провал теней: {crushed:.1f}% пикселей <= {shadow_floor}"
        )
    if p90 - p10 < 30:
        warnings.append(
            f"Узкий тональный диапазон: {p90 - p10:.0f} (p10={p10:.0f}, p90={p90:.0f})"
        )
    metrics["quality_warnings"] = warnings

    return metrics


def process_steps(
    input_path: str,
    machine_type: str = "laser_standard",
    config: dict | None = None,
    glow_size_override: int | None = None,
    glow_opacity_override: float | None = None,
    face_oval: dict | None = None,
    no_validate: bool = False,
) -> PipelineResult:
    """Полный пайплайн с доступом к каждому шагу.

    Не сохраняет файлы. Не печатает в stdout.
    Возвращает PipelineResult со всеми промежуточными изображениями и диагностикой.

    Конвейер (A.3 — исправленный порядок):
        glow → levels → face_brightness → unsharp → shadow_noise → vignette

    При legacy_step_order=True в конфиге:
        glow → levels → unsharp → face_brightness → shadow_noise → vignette

    Raises:
        FileNotFoundError: input_path не существует
        ValueError: невалидное изображение или конфиг
    """
    if config is None:
        config = load_config()

    # Валидация конфига
    warnings = validate_config(config)

    # Валидация входного изображения
    validate_image_input(input_path, config)

    # Загрузка
    img = Image.open(input_path).convert("RGBA")
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
    img_chromakey, subject_mask = remove_blue_background(
        img, threshold=threshold, fringe_radius=fringe_radius
    )

    # Закрыть исходное изображение — файловый дескриптор и память больше не нужны.
    img.close()

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
        warnings=warnings,
    )

    # B.1: Выполнение шагов через PipelineContext
    result = _run_pipeline_steps(
        ctx, proc_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        no_validate=no_validate,
        blue_ratio=blue_ratio,
    )
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
        )
        img_face_corrected, face_before, face_after, correction_factor = _apply_face_brightness(
            img_temp, ctx.machine_cfg, ctx.subject_mask, glow_size, ctx.face_mask,
        )
        img_sharpened = img_face_corrected  # В legacy-порядке unsharp уже применён
    else:
        # НОВЫЙ порядок (A.3): face_brightness ПЕРЕД unsharp
        img_face_corrected, face_before, face_after, correction_factor = _apply_face_brightness(
            img_leveled, ctx.machine_cfg, ctx.subject_mask, glow_size, ctx.face_mask,
        )
        img_sharpened = apply_unsharp_mask(
            img_face_corrected, subject_mask=ctx.subject_mask, analytics=ctx.analytics,
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
        img_sharpened = add_shadow_noise(
            img_sharpened, ctx.subject_mask,
            noise_min=shadow_noise_min, noise_max=shadow_noise_max,
            shadow_threshold=shadow_threshold,
        )

    # A.2: Shadow floor — отдельный шаг для impact
    # Предотвращает уход теней в 0 (игла застревает на чистом чёрном).
    # После shadow_noise: гарантирует что шум не создал значения < floor.
    shadow_floor = ctx.machine_cfg.get("shadow_floor", 0)
    if shadow_floor > 0 and ctx.machine_type == "impact" and HAS_NUMPY:
        arr = np.array(img_sharpened, dtype=np.float32)
        arr = clamp_masked(arr, ctx.subject_mask, vmin=shadow_floor)
        img_sharpened = Image.fromarray(arr.astype(np.uint8))
        logger.info("Shadow floor applied: %d (impact)", shadow_floor)

    # A.4: Hard clamp белой точки перед виньеткой
    white_ceiling = ctx.machine_cfg.get("white_ceiling", None)
    if white_ceiling is not None and HAS_NUMPY:
        arr = np.array(img_sharpened, dtype=np.float32)
        arr = clamp_masked(arr, ctx.subject_mask, vmax=white_ceiling)
        img_sharpened = Image.fromarray(arr.astype(np.uint8))
        logger.info("White ceiling clamp: %d", white_ceiling)

    # FIX #8: Stone gamma correction (SOP 5.1: gamma 0.8-0.9 для компенсации
    # визуального потемнения на камне). Применяется ПЕРЕД виньеткой,
    # ПОСЛЕ white_ceiling clamp. Только внутри маски субъекта.
    stone_gamma = ctx.machine_cfg.get("stone_gamma", None)
    if stone_gamma is not None and stone_gamma != 1.0 and HAS_NUMPY:
        arr = np.array(img_sharpened, dtype=np.float32)
        mask_bool = np.array(ctx.subject_mask) > 128
        arr = apply_stone_gamma_masked(arr, mask_bool, gamma=stone_gamma)
        img_sharpened = Image.fromarray(arr.astype(np.uint8))
        logger.info("Stone gamma applied: %.2f", stone_gamma)

    # 6. Vignette
    vign_cfg = ctx.config.get("vignette", {})
    img_final, arch_mask = apply_vignette(img_sharpened, width, height, vign_cfg)

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
        img_sharpened=img_sharpened,
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

    return check_face_brightness(
        img, face_target, subject_mask,
        glow_size=glow_size,
        face_region_top=face_region_top,
        highlight_start=highlight_start,
        white_ceiling=white_ceiling,
        face_mask_img=face_mask,  # C.3: маска лица из овала (приоритет над face_region_top)
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
    4. Сохраняет уменьшенное во временный файл (дескриптор закрыт ДО записи — Windows-safe)
    5. Вызывает process_steps() на уменьшенном
    6. Возвращает PipelineResult (все картинки уменьшенные)

    Glow фиксируется на середине диапазона для стабильности preview (D.1).
    """
    if config is None:
        config = load_config()

    machine_cfg = config.get("processing", {}).get(machine_type, {})

    # D.1: Фиксируем glow для стабильного preview (deterministic)
    glow_min = machine_cfg.get("glow_size_min", 40)
    glow_max = machine_cfg.get("glow_size_max", 80)
    glow_mid = (glow_min + glow_max) // 2

    opacity_min = machine_cfg.get("glow_opacity_min", 30)
    opacity_max = machine_cfg.get("glow_opacity_max", 40)
    opacity_mid = (opacity_min + opacity_max) // 2

    # Открываем изображение ОДИН раз
    img = Image.open(input_path)
    needs_resize = max(img.size) > max_size
    tmp_path = None

    try:
        if needs_resize:
            img.thumbnail((max_size, max_size), Image.LANCZOS)

            # D.2: Минимальная высота >= 200 для широких кадров
            if img.height < 200:
                ratio = 200 / img.height
                new_w = min(int(img.width * ratio), max_size * 3)
                # Перезагружаем и делаем правильный ресайз
                img.close()
                img = Image.open(input_path)
                img.thumbnail((new_w, 200), Image.LANCZOS)

            # Создаём временный файл, сразу закрываем дескриптор (Windows-safe)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp_name = tmp.name
            tmp.close()
            img.save(tmp_name, format="PNG")
            img.close()
            tmp_path = tmp_name
            work_path = tmp_path
        else:
            img.close()
            work_path = input_path

        return process_steps(
            input_path=work_path,
            machine_type=machine_type,
            config=config,
            glow_size_override=glow_mid,
            glow_opacity_override=opacity_mid,
            **kwargs,
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def process_export(
    input_path: str,
    output_path: str,
    machine_type: str = "laser_standard",
    config: dict | None = None,
    fmt: str = "bmp",
    overwrite: bool = True,
    **kwargs,
) -> PipelineResult:
    """Полная обработка + сохранение BMP/PNG.

    Вызывает process_steps(), затем сохраняет результат.
    По умолчанию сохраняет BMP (8-bit grayscale для laser_standard/impact,
    1-bit dithered для laser_80w) + PNG для предпросмотра.
    Промежуточные изображения освобождаются для экономии памяти.

    Args:
        input_path: путь к входному изображению
        output_path: путь к выходному файлу
        machine_type: тип станка
        config: конфигурация (None = загрузить из config.yaml)
        fmt: формат экспорта ('bmp', 'bmp_1bit', 'bmp_8bit', 'png')
        overwrite: D.7 — если False и файл существует, выбрасывает FileExistsError.
            CLI использует --overwrite флаг для управления.
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
        **kwargs,
    )

    # Сохранение BMP + PNG через export_result
    actual_path = export_result(
        result.img_final, output_path,
        machine_type=machine_type, fmt=fmt,
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
    """
    try:
        with Image.open(output_path) as img:
            if fmt in ("bmp", "bmp_8bit"):
                if img.mode not in ("L", "P"):
                    logger.warning(
                        "BMP validation: expected mode L or P, got %s", img.mode
                    )
            elif fmt == "bmp_1bit":
                if img.mode != "1":
                    logger.warning(
                        "BMP 1-bit validation: expected mode 1, got %s", img.mode
                    )
    except Exception as e:
        logger.error("BMP validation failed: cannot open %s: %s", output_path, e)


def process(input_path, output_path, machine_type="laser_standard",
            glow_size_override=None, glow_opacity_override=None,
            config=None, fmt="bmp", overwrite=True):
    """Обратная совместимая обёртка. CLI не ломается."""
    return process_export(
        input_path=input_path,
        output_path=output_path,
        machine_type=machine_type,
        config=config,
        fmt=fmt,
        overwrite=overwrite,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
    )
