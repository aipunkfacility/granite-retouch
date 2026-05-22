"""Полный пайплайн обработки портрета для гравировки."""

import logging
import os
from pathlib import Path

from PIL import Image

from retouch.config import DEFAULTS, load_config, validate_config
from retouch.validation.image import (
    ValidationError,
    validate_image_input,
    validate_blue_chromakey,
)
from retouch.processing.detection.chromakey import remove_blue_background
from retouch.processing.analysis.analysis import analyze_input, ImageAnalytics
from retouch.processing.detection.face_region import detect_face_oval, generate_face_mask, generate_hair_mask
from retouch.processing.output.export import export_result
from retouch.processing.core.plan import (
    PipelinePlan,
    ValidatedPlan,
    SafetyEnvelope,
    validate_plan,
    PROFILE_STANDARD,
    PROFILE_PRESERVE,
    PROFILE_DIAGNOSTIC,
)

from retouch.processing.core.context import PipelineContext, PipelineResult, _run_consistency_check
from retouch.processing.core.steps import (
    run_pipeline_steps as _run_pipeline_steps,
)

import numpy as np

logger = logging.getLogger(__name__)


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

    if hair_anomaly:
        ctx.warnings.append(f"hair_mask anomaly: {hair_anomaly_reason}")
        logger.warning("Hair mask anomaly: %s", hair_anomaly_reason)

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
    dither_method_1bit = machine_cfg.get("dither_method_1bit", "jarvis")

    actual_path = export_result(
        result.img_final, output_path,
        machine_type=machine_type, fmt=fmt,
        export_mode=export_mode,
        step_mm=step_mm,
        dither_method_1bit=dither_method_1bit,
        save_png_preview=True,
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
            debug_dir: str | None = None,
            profile: str | None = None) -> PipelineResult:
    """Обратная совместимая обёртка. CLI не ломается.

    Args:
        input_path: путь к входному изображению
        output_path: путь к выходному файлу
        machine_type: тип станка
        glow_size_override: ручное переопределение glow size
        glow_opacity_override: ручное переопределение glow opacity
        config: конфигурация
        fmt: формат экспорта
        overwrite: разрешить перезапись выходного файла
        no_validate: отключить валидацию
        face_oval: ручное переопределение овала лица
        debug_dir: директория для отладочных масок
        profile: профиль обработки (preserve/standard/diagnostic). Default: standard.
    """
    kwargs: dict = {}
    if profile is not None:
        kwargs["profile"] = profile
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
        face_oval=face_oval,
        debug_dir=debug_dir,
        **kwargs,
    )
