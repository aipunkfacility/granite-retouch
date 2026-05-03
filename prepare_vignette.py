import os
import argparse
import random
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageChops


# Defaults (used when config.yaml is not found or PyYAML is not installed)
DEFAULTS = {
    "processing": {
        "blue_threshold": 30,
        "laser": {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
            "brightness": 1.18,
            "face_brightness_target": [230, 245],
        },
        "impact": {
            "glow_size_min": 10, "glow_size_max": 25,
            "glow_opacity_min": 60, "glow_opacity_max": 80,
            "brightness": 1.12,
            "face_brightness_target": [220, 235],
            "shadow_noise": True,
        },
    },
    "vignette": {
        "vertical_offset": 0.10,
        "vertical_diameter": 0.50,
        "blur_radius": 60,
    },
}


def load_config(config_path=None):
    """Загрузить конфигурацию из config.yaml. Fallback на DEFAULTS."""
    if config_path is None:
        # Search in script directory and current directory
        script_dir = Path(__file__).parent
        candidates = [
            script_dir / "config.yaml",
            Path.cwd() / "config.yaml",
        ]
        for candidate in candidates:
            if candidate.is_file():
                config_path = candidate
                break

    if config_path and Path(config_path).is_file():
        if not HAS_YAML:
            print(f"Warning: PyYAML not installed, ignoring {config_path}. "
                  f"Install: pip install PyYAML")
            return DEFAULTS
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print(f"Config loaded: {config_path}")
        return config

    return DEFAULTS


def apply_retouch_processing(input_path, output_path, machine_type="laser",
                             glow_size_override=None, glow_opacity_override=None,
                             config=None):
    """Подготовка файла для гравировки: удаление хромакея, Inner Glow, виньетка."""
    if config is None:
        config = DEFAULTS

    proc = config.get("processing", DEFAULTS["processing"])
    vign = config.get("vignette", DEFAULTS["vignette"])
    blue_threshold = proc.get("blue_threshold", 30)
    machine_cfg = proc.get(machine_type, proc.get("laser", DEFAULTS["processing"]["laser"]))
    vign_cfg = vign if isinstance(vign, dict) else DEFAULTS["vignette"]

    # Load image
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size

    # 1. Remove Blue Background (Strictly to Black)
    data = list(img.getdata())
    new_data = []
    subject_mask = Image.new('L', (width, height), 0)
    mask_pixels = []

    for item in data:
        r, g, b, a = item
        # Blues & Cyans to transparent
        if b > r + blue_threshold and b > g + blue_threshold:
            new_data.append((0, 0, 0, 0))
            mask_pixels.append(0)
        else:
            new_data.append(item)
            mask_pixels.append(255)

    img.putdata(new_data)
    subject_mask.putdata(mask_pixels)

    # 2. Inner Glow (Contour Light) — parameters from config
    glow_size = glow_size_override or random.randint(
        machine_cfg.get("glow_size_min", 40),
        machine_cfg.get("glow_size_max", 80),
    )
    glow_opacity = (glow_opacity_override / 100) if glow_opacity_override else (
        random.randint(
            machine_cfg.get("glow_opacity_min", 30),
            machine_cfg.get("glow_opacity_max", 40),
        ) / 100
    )
    brightness_factor = machine_cfg.get("brightness", 1.18)

    # Create mask for internal glow
    inv_mask = ImageOps.invert(subject_mask)
    glow_mask = inv_mask.filter(ImageFilter.GaussianBlur(radius=glow_size))
    glow_mask = ImageChops.multiply(glow_mask, subject_mask)
    glow_mask = glow_mask.point(lambda p: p * glow_opacity)

    # 3. Finalization (Grayscale, Levels, Unsharp)
    img_gray = img.convert("L")
    img_with_glow = Image.composite(Image.new('L', (width, height), 255), img_gray, glow_mask)

    # Levels (brightness from config)
    enhancer = ImageEnhance.Brightness(img_with_glow)
    img_leveled = enhancer.enhance(brightness_factor)

    # Unsharp Mask
    img_final = img_leveled.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=0))

    # 4. Arch/Vignette Mask (scalable, from config)
    arch = Image.new('L', (width, height), 0)
    draw_arch = ImageDraw.Draw(arch)
    v_offset = height * vign_cfg.get("vertical_offset", 0.10)
    v_diameter = height * vign_cfg.get("vertical_diameter", 0.50)
    blur_radius = vign_cfg.get("blur_radius", 60)
    draw_arch.ellipse(
        [-width * 0.2, height - v_offset - v_diameter, width * 1.2, height - v_offset + v_diameter * 0.38],
        fill=255
    )
    arch_mask = arch.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Composite Final Image over black
    background = Image.new('RGB', (width, height), (0, 0, 0))
    background.paste(img_final, (0, 0), arch_mask)

    # Save results
    output_png = output_path.replace(".tiff", ".png").replace(".tif", ".png")
    background.save(output_path, "TIFF")
    background.save(output_png, "PNG")
    print(f"Processed image saved to {output_path}")
    print(f"Machine: {machine_type}, Glow: {glow_size}px/{glow_opacity:.0%}, "
          f"Brightness: {brightness_factor}")


def main():
    parser = argparse.ArgumentParser(
        description="granite-retouch — подготовка файла для гравировки"
    )
    parser.add_argument("--input", "-i", required=True,
        help="Путь к входному изображению (PNG с синим хромакеем)")
    parser.add_argument("--output", "-o", required=True,
        help="Путь к выходному файлу (TIFF)")
    parser.add_argument("--machine", "-m",
        choices=["laser", "impact"], default="laser",
        help="Тип станка гравировки (default: laser)")
    parser.add_argument("--glow-size", type=int,
        help="Переопределить размер Inner Glow (px)")
    parser.add_argument("--glow-opacity", type=int,
        help="Переопределить opacity Inner Glow (%%)")
    parser.add_argument("--config", "-c",
        help="Путь к config.yaml (default: auto-detect)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        parser.error(f"Входной файл не найден: {args.input}")

    config = load_config(args.config)

    apply_retouch_processing(
        args.input, args.output,
        machine_type=args.machine,
        glow_size_override=args.glow_size,
        glow_opacity_override=args.glow_opacity,
        config=config,
    )


if __name__ == "__main__":
    main()
