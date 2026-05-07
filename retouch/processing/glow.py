"""Inner Glow (Contour Light) — контурное свечение."""

import random
from PIL import Image, ImageFilter, ImageOps, ImageChops


def _calculate_glow_params(analytics: dict, machine_type: str) -> tuple:
    """P3: Рассчитать адаптивные параметры glow на основе аналитики.

    Args:
        analytics: dict с метриками от analyze_input()
        machine_type: тип станка ('laser_standard', 'laser_80w', 'impact')

    Returns:
        tuple: (glow_size, glow_opacity_percent) — размер и непрозрачность в %%
    """
    if machine_type == 'laser_80w':
        return (20, 15)

    if machine_type == 'impact':
        separation = analytics.get('subject_separation', 150)
        if separation > 80:
            return (random.randint(10, 18), random.randint(60, 70))
        elif separation > 40:
            return (random.randint(15, 25), random.randint(65, 75))
        else:
            return (random.randint(20, 30), random.randint(70, 85))

    # laser_standard: by tonal_range
    tonal_range = analytics.get('tonal_range', 100)
    if tonal_range > 120:
        return (random.randint(30, 50), random.randint(20, 30))
    elif tonal_range > 80:
        return (random.randint(40, 60), random.randint(30, 40))
    else:
        return (random.randint(50, 80), random.randint(35, 45))


def apply_inner_glow(img_gray, subject_mask, machine_cfg,
                     glow_size_override=None, glow_opacity_override=None,
                     analytics=None, machine_type=None):
    """Применить Inner Glow к grayscale-изображению.

    Создаёт контурное свечение внутри маски субъекта.
    Параметры зависят от типа станка (laser: широкий/мягкий, impact: узкий/яркий).

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        subject_mask: PIL.Image в режиме L (маска субъекта, 255=субъект)
        machine_cfg: dict с параметрами станка из config.yaml
        glow_size_override: переопределить размер glow (px)
        glow_opacity_override: переопределить opacity glow (%%)
        analytics: dict от analyze_input() — если передан вместе с
            machine_type, параметры glow рассчитываются адаптивно (P3).
        machine_type: str — тип станка. Используется только вместе с analytics.

    Returns:
        PIL.Image: grayscale с Inner Glow
        int: glow_size (px)
        float: glow_opacity (0.0–1.0)
    """
    width, height = img_gray.size

    # Определяем параметры glow
    if (analytics is not None and machine_type is not None
            and glow_size_override is None and glow_opacity_override is None):
        # P3: Адаптивные параметры из аналитики
        glow_size, glow_opacity_pct = _calculate_glow_params(analytics, machine_type)
        glow_opacity = glow_opacity_pct / 100
    else:
        # Старое поведение: random из конфига или override
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
