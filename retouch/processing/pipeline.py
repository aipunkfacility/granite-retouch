"""Полный пайплайн обработки портрета для гравировки."""

import os

from PIL import Image

from retouch.config import DEFAULTS, load_config
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


def process(input_path, output_path, machine_type="laser",
            glow_size_override=None, glow_opacity_override=None,
            config=None):
    """Полный пайплайн подготовки файла для гравировки.

    Pipeline:
    1. Валидация входного изображения
    2. Валидация синего хромакея
    3. Удаление синего фона + fringe removal
    4. Inner Glow (параметры зависят от machine_type)
    5. Grayscale + Levels + Unsharp Mask
    6. Контроль яркости лица
    7. Арховая виньетка
    8. Валидация результата
    9. Сохранение TIFF + PNG
    """
    if config is None:
        config = DEFAULTS

    proc = config.get("processing", DEFAULTS["processing"])
    vign = config.get("vignette", DEFAULTS["vignette"])
    blue_threshold = proc.get("blue_threshold", 30)
    min_blue_ratio = proc.get("min_blue_ratio", 0.15)
    result_min_black = proc.get("result_min_black_ratio", 0.25)
    fringe_radius = proc.get("fringe_radius", 3)
    machine_cfg = proc.get(machine_type, proc.get("laser", DEFAULTS["processing"]["laser"]))
    vign_cfg = vign if isinstance(vign, dict) else DEFAULTS["vignette"]

    # 1. Validate input
    validate_image_input(input_path, config)

    # 2. Load image
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size
    print(f"Image loaded: {width}x{height}, mode: {img.mode}")
    print(f"numpy: {'enabled' if HAS_NUMPY else 'not installed (install: uv pip install numpy)'}")

    # 3. Validate chromakey
    blue_ratio = validate_blue_chromakey(img, threshold=blue_threshold,
                                         min_blue_ratio=min_blue_ratio)
    print(f"Chromakey check passed: {blue_ratio:.1%} blue pixels")

    # 4. Remove blue background + fringe
    img, subject_mask = remove_blue_background(img, threshold=blue_threshold,
                                                fringe_radius=fringe_radius)
    print(f"Blue background removed (fringe_radius: {fringe_radius})")

    # 5. Inner Glow
    brightness_factor = machine_cfg.get("brightness", 1.18)
    img_gray = img.convert("L")
    img_with_glow, glow_size, glow_opacity = apply_inner_glow(
        img_gray, subject_mask, machine_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
    )

    # 6. Levels + Unsharp
    img_leveled = apply_levels(img_with_glow, brightness_factor)
    img_final = apply_unsharp_mask(img_leveled)

    # 7. Face brightness control
    face_target = machine_cfg.get("face_brightness_target", [230, 245])
    img_final = check_face_brightness(img_final, face_target, subject_mask)

    # 8. Vignette
    background, arch_mask = apply_vignette(img_final, width, height, vign_cfg)

    # 9. Validate result
    black_ratio = validate_result_black_ratio(background, min_black_ratio=result_min_black)
    print(f"Result check passed: {black_ratio:.1%} black background")

    # 10. Save
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    background.save(output_path, "TIFF")

    output_png = output_path.replace(".tiff", ".png").replace(".tif", ".png")
    if output_png == output_path:
        output_png = output_path + ".png"
    background.save(output_png, "PNG")

    print(f"Saved: {output_path}")
    print(f"Saved: {output_png}")
    print(f"Machine: {machine_type}, Glow: {glow_size}px/{glow_opacity:.0%}, "
          f"Brightness: {brightness_factor}")
