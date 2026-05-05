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
from retouch.processing.glow import apply_inner_glow
from retouch.processing.levels import apply_levels, apply_unsharp_mask, check_face_brightness
from retouch.processing.vignette import apply_vignette

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Результат пайплайна — все промежуточные этапы + диагностика."""

    # Промежуточные изображения (PIL.Image | None после release_intermediates)
    img_chromakey: Image.Image | None       # После хромакея (RGBA)
    img_gray: Image.Image | None            # После конвертации в L
    img_glow: Image.Image | None            # После Inner Glow (L)
    img_leveled: Image.Image | None         # После Levels + Unsharp (L)
    img_face_corrected: Image.Image | None  # После face brightness correction (L)
    img_final: Image.Image                  # После виньетки (RGB) — всегда сохраняется
    arch_mask: Image.Image | None           # Маска виньетки (L)
    subject_mask: Image.Image | None        # Маска субъекта (L)

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
    warnings: list[str] = field(default_factory=list)

    def release_intermediates(self):
        """Освободить память от промежуточных изображений.

        После вызова доступ к img_chromakey, img_gray, img_glow, img_leveled,
        img_face_corrected, arch_mask, subject_mask вернёт None.
        img_final остаётся доступным — он нужен для сохранения.
        """
        self.img_chromakey = None
        self.img_gray = None
        self.img_glow = None
        self.img_leveled = None
        self.img_face_corrected = None
        self.arch_mask = None
        self.subject_mask = None


def process_steps(
    input_path: str,
    machine_type: str = "laser",
    config: dict | None = None,
    glow_size_override: int | None = None,
    glow_opacity_override: float | None = None,
    no_validate: bool = False,
) -> PipelineResult:
    """Полный пайплайн с доступом к каждому шагу.

    Не сохраняет файлы. Не печатает в stdout.
    Возвращает PipelineResult со всеми промежуточными изображениями и диагностикой.

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

    # A2: Закрыть исходное изображение — файловый дескриптор и память больше не нужны.
    # После remove_blue_background() результат в img_chromakey, исходный img не используется.
    img.close()

    # 2. Grayscale
    img_gray = img_chromakey.convert("L")

    # 3. Inner Glow
    # ВАЖНО: имена параметров — glow_size_override / glow_opacity_override
    # (соответствуют текущей сигнатуре apply_inner_glow в glow.py)
    machine_cfg = proc_cfg.get(machine_type, {})
    img_glow, glow_size, glow_opacity = apply_inner_glow(
        img_gray, subject_mask, machine_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
    )

    # 4. Levels + Unsharp
    brightness_factor = machine_cfg.get("brightness", 1.0)
    img_leveled = apply_levels(img_glow, brightness_factor=brightness_factor)
    img_leveled = apply_unsharp_mask(img_leveled)

    # 5. Face brightness correction
    # Support both old list format [min, max] and new separate keys
    if "face_brightness_target" in machine_cfg:
        face_target = machine_cfg["face_brightness_target"]
    else:
        t_min = machine_cfg.get("face_brightness_target_min", 200)
        t_max = machine_cfg.get("face_brightness_target_max", 230)
        face_target = [t_min, t_max]
    face_region_top = machine_cfg.get("face_region_top", 0.45)
    highlight_start = machine_cfg.get("highlight_start", 200)
    img_face_corrected, face_before, face_after, correction_factor = check_face_brightness(
        img_leveled, face_target, subject_mask,
        glow_size=glow_size,
        face_region_top=face_region_top,
        highlight_start=highlight_start,
    )

    # 6. Vignette
    vign_cfg = config.get("vignette", {})
    img_final, arch_mask = apply_vignette(img_face_corrected, width, height, vign_cfg)

    # 7. Валидация результата
    # ВАЖНО: передаём img_final, а не Image.new — иначе валидация всегда 100%
    black_ratio = 0.0
    if not no_validate:
        result_min_black = proc_cfg.get("result_min_black_ratio", 0.25)
        black_ratio = validate_result_black_ratio(img_final, min_black_ratio=result_min_black)

    logger.info(
        "Pipeline complete: %dx%d, glow=%dpx/%.0f%%, face=%.0f→%.0f",
        width, height, glow_size, glow_opacity * 100, face_before, face_after,
    )

    return PipelineResult(
        img_chromakey=img_chromakey,
        img_gray=img_gray,
        img_glow=img_glow,
        img_leveled=img_leveled,
        img_face_corrected=img_face_corrected,
        img_final=img_final,
        arch_mask=arch_mask,
        subject_mask=subject_mask,
        glow_size=glow_size,
        glow_opacity=glow_opacity,
        face_brightness_before=face_before,
        face_brightness_after=face_after,
        face_correction_factor=correction_factor,
        black_ratio=black_ratio,
        blue_ratio=blue_ratio,
        width=width,
        height=height,
        warnings=warnings,
    )


def process_preview(
    input_path: str,
    machine_type: str = "laser",
    config: dict | None = None,
    max_size: int = 768,
    **kwargs,
) -> PipelineResult:
    """Предпросмотр — уменьшенная копия для Web UI.

    1. Загружает полное изображение ОДИН раз (A5)
    2. Уменьшает до max_size по длинной стороне (thumbnail), если нужно
    3. Сохраняет уменьшенное во временный файл (дескриптор закрыт ДО записи — Windows-safe)
    4. Вызывает process_steps() на уменьшенном
    5. Возвращает PipelineResult (все картинки уменьшенные)

    Glow фиксируется на середине диапазона для стабильности preview:
    glow_size = (glow_size_min + glow_size_max) // 2
    """
    if config is None:
        config = load_config()

    machine_cfg = config.get("processing", {}).get(machine_type, {})

    # Фиксируем glow для стабильного preview
    glow_min = machine_cfg.get("glow_size_min", 40)
    glow_max = machine_cfg.get("glow_size_max", 80)
    glow_mid = (glow_min + glow_max) // 2

    opacity_min = machine_cfg.get("glow_opacity_min", 30)
    opacity_max = machine_cfg.get("glow_opacity_max", 40)
    # NOTE: opacity_mid — целое число процентов (0–100), apply_inner_glow()
    # конвертирует в float 0.0–1.0 через glow_opacity_override / 100.
    # Не меняем на float здесь — ломает CLI-флаг --glow-opacity (целое число %).
    opacity_mid = (opacity_min + opacity_max) // 2

    # A5: Открываем изображение ОДИН раз — решаем, нужен ли ресайз,
    # тут же делаем thumbnail, сохраняем, закрываем.
    img = Image.open(input_path)
    needs_resize = max(img.size) > max_size
    tmp_path = None

    try:
        if needs_resize:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
            # Создаём временный файл, сразу закрываем дескриптор (Windows-safe)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp_name = tmp.name
            tmp.close()  # Закрыть дескриптор ДО записи — иначе PermissionError на Windows
            img.save(tmp_name, format="PNG")
            img.close()  # Освободить дескриптор после записи
            tmp_path = tmp_name
            work_path = tmp_path
        else:
            img.close()  # Освободить дескриптор даже когда ресайз не нужен
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
    machine_type: str = "laser",
    config: dict | None = None,
    **kwargs,
) -> PipelineResult:
    """Полная обработка + сохранение TIFF/PNG (текущее поведение CLI).

    Вызывает process_steps(), затем сохраняет результат.
    Промежуточные изображения освобождаются для экономии памяти.
    """
    result = process_steps(
        input_path=input_path,
        machine_type=machine_type,
        config=config,
        **kwargs,
    )

    # Сохранение TIFF + PNG
    tiff_path = output_path
    png_path = str(Path(output_path).with_suffix(".png"))  # Безопасная замена расширения
    result.img_final.save(tiff_path, format="TIFF", compression="lzw")
    result.img_final.save(png_path, format="PNG")

    logger.info("Сохранено: %s, %s", tiff_path, png_path)

    # Освобождаем промежуточные для экономии RAM
    result.release_intermediates()
    return result


def process(input_path, output_path, machine_type="laser",
            glow_size_override=None, glow_opacity_override=None,
            config=None):
    """Обратная совместимая обёртка. CLI не ломается."""
    return process_export(
        input_path=input_path,
        output_path=output_path,
        machine_type=machine_type,
        config=config,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
    )
