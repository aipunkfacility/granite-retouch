"""Арховая виньетка (Memorial Arch)."""

from PIL import Image, ImageDraw, ImageFilter


def apply_vignette(img_gray, width, height, vign_cfg):
    """Наложить арховую виньетку на grayscale-изображение.

    Эллипс вынесен выше изображения — голова всегда видна.
    Только нижние углы плавно затемняются.

    Args:
        img_gray: PIL.Image в режиме L
        width: ширина изображения
        height: высота изображения
        vign_cfg: dict с параметрами виньетки из config.yaml

    Returns:
        PIL.Image: RGB-изображение на чёрном фоне с виньеткой
    """
    v_offset = height * vign_cfg.get("vertical_offset", 0.10)
    v_diameter = height * vign_cfg.get("vertical_diameter", 0.50)
    blur_radius = vign_cfg.get("blur_radius", 60)
    headroom = height * vign_cfg.get("headroom", 0.6)
    h_oversize = width * vign_cfg.get("horizontal_oversize", 0.2)

    arch_bottom_y = height - v_offset
    arch_top_y = arch_bottom_y - v_diameter - headroom

    # Draw arch mask
    arch = Image.new('L', (width, height), 0)
    draw_arch = ImageDraw.Draw(arch)
    draw_arch.ellipse(
        [-h_oversize, arch_top_y, width + h_oversize, arch_bottom_y],
        fill=255
    )
    arch_mask = arch.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Composite over black
    background = Image.new('RGB', (width, height), (0, 0, 0))
    background.paste(img_gray, (0, 0), arch_mask)

    return background, arch_mask
