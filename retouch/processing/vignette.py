"""Арховая виньетка (Memorial Arch)."""

from PIL import Image, ImageDraw, ImageFilter


def generate_arch_mask(width: int, height: int, vign_cfg: dict) -> Image.Image:
    """Сгенерировать маску арховой виньетки (L, 0-255).

    Возвращает размытую маску без композитинга - только эллипс + GaussianBlur.
    Переиспользуемая функция для пайплайна и API-эндпоинта маски.

    Args:
        width: ширина маски в пикселях
        height: высота маски в пикселях
        vign_cfg: dict с параметрами виньетки из config.yaml

    Returns:
        PIL.Image: маска в режиме L (0 = чёрный фон, 255 = видимая область)
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
    return arch.filter(ImageFilter.GaussianBlur(radius=blur_radius))


def apply_vignette(img_gray, width, height, vign_cfg):
    """Наложить арховую виньетку на grayscale-изображение.

    Эллипс вынесен выше изображения - голова всегда видна.
    Только нижние углы плавно затемняются.

    Args:
        img_gray: PIL.Image в режиме L
        width: ширина изображения
        height: высота изображения
        vign_cfg: dict с параметрами виньетки из config.yaml

    Returns:
        tuple: (PIL.Image L-изображение на чёрном фоне, PIL.Image маска виньетки L)
    """
    arch_mask = generate_arch_mask(width, height, vign_cfg)

    # Composite over black, staying in L mode
    background = Image.new('L', (width, height), 0)
    result = Image.composite(img_gray, background, arch_mask)

    return result, arch_mask
