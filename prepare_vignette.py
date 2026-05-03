import os
import argparse
import random
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageChops


def apply_retouch_processing(input_path, output_path, machine_type="laser",
                             glow_size_override=None, glow_opacity_override=None):
    """Подготовка файла для гравировки: удаление хромакея, Inner Glow, виньетка."""
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
        if b > r + 30 and b > g + 30:
            new_data.append((0, 0, 0, 0))
            mask_pixels.append(0)
        else:
            new_data.append(item)
            mask_pixels.append(255)

    img.putdata(new_data)
    subject_mask.putdata(mask_pixels)

    # 2. Inner Glow (Contour Light)
    # Parameters depend on machine type
    if machine_type == "impact":
        glow_size = glow_size_override or random.randint(10, 25)
        glow_opacity = (glow_opacity_override / 100) if glow_opacity_override else random.randint(60, 80) / 100
        brightness_factor = 1.12
    else:  # laser
        glow_size = glow_size_override or random.randint(40, 80)
        glow_opacity = (glow_opacity_override / 100) if glow_opacity_override else random.randint(30, 40) / 100
        brightness_factor = 1.18

    # Create mask for internal glow
    inv_mask = ImageOps.invert(subject_mask)
    glow_mask = inv_mask.filter(ImageFilter.GaussianBlur(radius=glow_size))
    glow_mask = ImageChops.multiply(glow_mask, subject_mask)
    glow_mask = glow_mask.point(lambda p: p * glow_opacity)

    # 3. Finalization (Grayscale, Levels, Unsharp)
    img_gray = img.convert("L")
    img_with_glow = Image.composite(Image.new('L', (width, height), 255), img_gray, glow_mask)

    # Levels (brightness adjustment per machine type)
    enhancer = ImageEnhance.Brightness(img_with_glow)
    img_leveled = enhancer.enhance(brightness_factor)

    # Unsharp Mask
    img_final = img_leveled.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=0))

    # 4. Arch/Vignette Mask (scalable)
    arch = Image.new('L', (width, height), 0)
    draw_arch = ImageDraw.Draw(arch)
    v_offset = height * 0.10    # 10% from bottom
    v_diameter = height * 0.50  # 50% of height
    draw_arch.ellipse(
        [-width * 0.2, height - v_offset - v_diameter, width * 1.2, height - v_offset + v_diameter * 0.38],
        fill=255
    )
    arch_mask = arch.filter(ImageFilter.GaussianBlur(radius=60))

    # Composite Final Image over black
    background = Image.new('RGB', (width, height), (0, 0, 0))
    background.paste(img_final, (0, 0), arch_mask)

    # Save results
    output_png = output_path.replace(".tiff", ".png").replace(".tif", ".png")
    background.save(output_path, "TIFF")
    background.save(output_png, "PNG")
    print(f"Processed image saved to {output_path}")
    print(f"Machine type: {machine_type}, Glow: {glow_size}px/{glow_opacity:.0%}")


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
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        parser.error(f"Входной файл не найден: {args.input}")

    apply_retouch_processing(
        args.input, args.output,
        machine_type=args.machine,
        glow_size_override=args.glow_size,
        glow_opacity_override=args.glow_opacity,
    )


if __name__ == "__main__":
    main()
