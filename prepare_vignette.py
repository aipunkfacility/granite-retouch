import os
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageChops

def apply_memorial_processing(input_path, output_path, machine_type="laser"):
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
    # For Laser: Size 40-80px, Opacity 30-40%
    glow_size = 60
    glow_opacity = 0.35
    
    # Create mask for internal glow
    inv_mask = ImageOps.invert(subject_mask)
    glow_mask = inv_mask.filter(ImageFilter.GaussianBlur(radius=glow_size))
    glow_mask = ImageChops.multiply(glow_mask, subject_mask)
    glow_mask = glow_mask.point(lambda p: p * glow_opacity)
    
    # 3. Finalization (Grayscale, Levels, Unsharp)
    img_gray = img.convert("L")
    img_with_glow = Image.composite(Image.new('L', (width, height), 255), img_gray, glow_mask)
    
    # Levels (Highlights to ~240)
    enhancer = ImageEnhance.Brightness(img_with_glow)
    img_leveled = enhancer.enhance(1.18)
    
    # Unsharp Mask
    img_final = img_leveled.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=0))
    
    # 4. Arch/Vignette Mask
    arch = Image.new('L', (width, height), 0)
    draw_arch = ImageDraw.Draw(arch)
    draw_arch.ellipse([-width * 0.2, -height * 0.1, width * 1.2, height * 0.88], fill=255)
    arch_mask = arch.filter(ImageFilter.GaussianBlur(radius=60))
    
    # Composite Final Image over black
    background = Image.new('RGB', (width, height), (0, 0, 0))
    background.paste(img_final, (0, 0), arch_mask)
    
    # Save results
    background.save(output_path, "TIFF")
    background.save(output_path.replace(".tiff", ".png"), "PNG")
    print(f"Full memorial-processed image saved to {output_path}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, "generated", "ai.png")
    output_path = os.path.join(script_dir, "generated", "final_vignette.tiff")
    apply_memorial_processing(input_path, output_path)
