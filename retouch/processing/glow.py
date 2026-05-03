"""Inner Glow (Contour Light) — контурное свечение."""

import random
from PIL import Image, ImageFilter, ImageOps, ImageChops


def apply_inner_glow(img_gray, subject_mask, machine_cfg,
                     glow_size_override=None, glow_opacity_override=None):
    """Применить Inner Glow к grayscale-изображению.

    Создаёт контурное свечение внутри маски субъекта.
    Параметры зависят от типа станка (laser: широкий/мягкий, impact: узкий/яркий).

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        subject_mask: PIL.Image в режиме L (маска субъекта, 255=субъект)
        machine_cfg: dict с параметрами станка из config.yaml
        glow_size_override: переопределить размер glow (px)
        glow_opacity_override: переопределить opacity glow (%%)

    Returns:
        PIL.Image: grayscale с Inner Glow
    """
    width, height = img_gray.size

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

    # Create glow mask
    inv_mask = ImageOps.invert(subject_mask)
    glow_mask = inv_mask.filter(ImageFilter.GaussianBlur(radius=glow_size))
    glow_mask = ImageChops.multiply(glow_mask, subject_mask)
    glow_mask = glow_mask.point(lambda p: p * glow_opacity)

    # Composite glow onto grayscale
    img_with_glow = Image.composite(
        Image.new('L', (width, height), 255), img_gray, glow_mask
    )

    return img_with_glow, glow_size, glow_opacity
