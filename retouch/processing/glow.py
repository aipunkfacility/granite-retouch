"""Glow (Contour Light) — контурное свечение: inner и outer."""

import warnings

from PIL import Image, ImageFilter, ImageOps, ImageChops

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _calculate_glow_params(analytics: dict, machine_type: str,
                           machine_cfg: dict | None = None) -> tuple:
    """D.1: Рассчитать детерминированные параметры glow на основе аналитики.

    Рандомизация убрана — glow всегда одинаковый при одинаковых входных
    данных. Это гарантирует preview-export consistency (D.1).

    Args:
        analytics: dict с метриками от analyze_input()
        machine_type: тип станка ('laser_standard', 'laser_80w', 'impact')
        machine_cfg: dict — параметры станка из config.yaml. Для laser_80w
            glow_size_min/max и glow_opacity_min/max читаются из конфига
            вместо захардкоженных значений.

    Returns:
        tuple: (glow_size, glow_opacity_percent) — размер и непрозрачность в %%
    """
    if machine_type == 'laser_80w':
        cfg = machine_cfg or {}
        glow_min = cfg.get('glow_size_min', 15)
        glow_max = cfg.get('glow_size_max', 25)
        opacity_min = cfg.get('glow_opacity_min', 10)
        opacity_max = cfg.get('glow_opacity_max', 20)
        return ((glow_min + glow_max) // 2, (opacity_min + opacity_max) // 2)

    if machine_type == 'impact':
        separation = analytics.get('subject_separation', 150)
        if separation > 80:
            return (14, 65)   # midpoint(10..18), midpoint(60..70)
        elif separation > 40:
            return (20, 70)   # midpoint(15..25), midpoint(65..75)
        else:
            return (25, 77)   # midpoint(20..30), midpoint(70..85)

    # laser_standard: by tonal_range
    tonal_range = analytics.get('tonal_range', 100)
    if tonal_range > 120:
        return (40, 25)   # midpoint(30..50), midpoint(20..30)
    elif tonal_range > 80:
        return (50, 35)   # midpoint(40..60), midpoint(30..40)
    else:
        return (65, 40)   # midpoint(50..80), midpoint(35..45)


def apply_outer_glow(img_gray, subject_mask, glow_size=20, glow_opacity=0.35):
    """Применить Outer Glow — свечение наружу от контура субъекта.

    Алгоритм:
      1. Размываем маску субъекта → градиент от края наружу
      2. Вычитаем оригинальную маску → остаётся только свечение ВНЕ субъекта
      3. Масштабируем по opacity
      4. Composite: белое свечение поверх оригинала через glow_mask

    Результат: мягкое белое свечение вокруг контура портрета,
    затухающее к периферии. Именно это нужно для компенсации
    «съедания» границ камнем (принцип 4: stone eats boundaries).

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        subject_mask: PIL.Image в режиме L (маска субъекта, 255=субъект)
        glow_size: размер glow в пикселях (радиус GaussianBlur)
        glow_opacity: непрозрачность (0.0–1.0)

    Returns:
        PIL.Image: grayscale с Outer Glow
    """
    width, height = img_gray.size

    # Размываем маску субъекта — получаем градиент от края наружу
    blurred_mask = subject_mask.filter(ImageFilter.GaussianBlur(radius=glow_size))

    # Вычитаем оригинальную маску → остаётся только область ВНЕ субъекта
    # (внутри субъекта blurred ≈ 255, после вычитания → 0)
    glow_mask = ImageChops.subtract(blurred_mask, subject_mask)

    # Масштабируем по opacity (numpy вместо point(lambda) — ~10x быстрее)
    if HAS_NUMPY:
        glow_arr = np.array(glow_mask, dtype=np.float32)
        glow_arr = np.minimum(255.0, glow_arr * glow_opacity).astype(np.uint8)
        glow_mask = Image.fromarray(glow_arr)
    else:
        glow_mask = glow_mask.point(lambda p: min(255, int(p * glow_opacity)))

    # Composite: белое свечение через glow_mask поверх оригинала
    img_with_glow = Image.composite(
        Image.new('L', (width, height), 255), img_gray, glow_mask
    )

    return img_with_glow


def apply_inner_glow_algorithm(img_gray, subject_mask, glow_size=20,
                               glow_opacity=0.80, glow_color=255):
    """Применить настоящий Inner Glow — свечение внутрь от контура субъекта.

    Алгоритм: shrink mask → edge = mask & ~shrunk → blur edge → composite.
    Свечение появляется ВНУТРИ контура субъекта, затухая к центру.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        subject_mask: PIL.Image в режиме L (маска субъекта, 255=субъект)
        glow_size: размер glow в пикселях
        glow_opacity: непрозрачность (0.0–1.0)
        glow_color: цвет свечения (0–255, по умолчанию белый)

    Returns:
        PIL.Image: grayscale с Inner Glow
    """
    if not HAS_NUMPY:
        # Pillow fallback — упрощённая версия
        blurred_mask = subject_mask.filter(
            ImageFilter.GaussianBlur(radius=glow_size)
        )
        # Композит: яркое свечение через размытую маску
        glow_layer = Image.new('L', img_gray.size, glow_color)
        result = Image.composite(glow_layer, img_gray, blurred_mask)
        if glow_opacity < 1.0:
            result = Image.blend(img_gray, result, glow_opacity)
        return result

    mask_arr = np.array(subject_mask) > 128

    # Сжимаем маску — внутренний край = разница
    # GaussianBlur вместо binary_erosion — изотропная, без лесенки
    from scipy.ndimage import gaussian_filter
    iterations = max(1, glow_size // 2)
    inv = 1.0 - mask_arr.astype(np.float32)
    blurred = gaussian_filter(inv, sigma=iterations)
    shrunk = blurred < 0.5

    # Edge = внутренний край (контур внутри маски)
    edge = mask_arr & ~shrunk

    # Размываем край для плавного затухания к центру
    edge_img = Image.fromarray(edge.astype(np.uint8) * 255)
    edge_blurred = edge_img.filter(ImageFilter.GaussianBlur(glow_size // 2))

    # Composite: белый через размытый край поверх оригинала
    glow_layer = Image.new("L", img_gray.size, glow_color)
    result = Image.composite(glow_layer, img_gray, edge_blurred)

    if glow_opacity < 1.0:
        result = Image.blend(img_gray, result, glow_opacity)

    return result


def apply_glow(img_gray, subject_mask, machine_cfg,
                     glow_size_override=None, glow_opacity_override=None,
                     analytics=None, machine_type=None,
                     glow_style=None):
    """Применить Glow к grayscale-изображению.

    Поддерживает два стиля:
    - 'outer': свечение наружу (старое поведение, до рефакторинга A.5)
    - 'inner': свечение внутрь (настоящий inner glow, A.5)

    По умолчанию используется стиль из machine_cfg['glow_style'] или 'outer'
    (обратная совместимость).

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        subject_mask: PIL.Image в режиме L (маска субъекта, 255=субъект)
        machine_cfg: dict с параметрами станка из config.yaml
        glow_size_override: переопределить размер glow (px)
        glow_opacity_override: переопределить opacity glow (%%)
        analytics: dict от analyze_input() — если передан вместе с
            machine_type, параметры glow рассчитываются адаптивно (P3).
        machine_type: str — тип станка. Используется только вместе с analytics.
        glow_style: 'inner' | 'outer' | None (из конфига)

    Returns:
        PIL.Image: grayscale с Glow
        int: glow_size (px)
        float: glow_opacity (0.0–1.0)
    """
    # Определяем стиль glow
    style = glow_style or machine_cfg.get("glow_style", "outer")

    # Определяем параметры glow
    if (analytics is not None and machine_type is not None
            and glow_size_override is None and glow_opacity_override is None):
        # P3: Адаптивные параметры из аналитики
        glow_size, glow_opacity_pct = _calculate_glow_params(analytics, machine_type, machine_cfg)
        glow_opacity = glow_opacity_pct / 100
    else:
        # D.1: Детерминированный fallback — midpoint диапазона из конфига
        glow_size_min = machine_cfg.get("glow_size_min", 40)
        glow_size_max = machine_cfg.get("glow_size_max", 80)
        glow_opacity_min = machine_cfg.get("glow_opacity_min", 30)
        glow_opacity_max = machine_cfg.get("glow_opacity_max", 40)

        glow_size = glow_size_override or (glow_size_min + glow_size_max) // 2
        glow_opacity = (glow_opacity_override / 100) if glow_opacity_override else (
            (glow_opacity_min + glow_opacity_max) // 2 / 100
        )

    # Применяем выбранный стиль
    if style == "inner":
        result = apply_inner_glow_algorithm(
            img_gray, subject_mask,
            glow_size=glow_size,
            glow_opacity=glow_opacity,
        )
    else:
        # 'outer' — старое поведение (обратная совместимость)
        result = apply_outer_glow(
            img_gray, subject_mask,
            glow_size=glow_size,
            glow_opacity=glow_opacity,
        )

    return result, glow_size, glow_opacity


# A.5: Backward-compatible alias — устаревшее обманчивое имя.
# apply_glow() — диспетчер (inner/outer), а не только inner glow.
# AUDIT-5.5: alias удалён, доступ через __getattr__ с DeprecationWarning.


def __getattr__(name):
    """AUDIT-5.5: Ленивый deprecated alias для apply_inner_glow."""
    if name == "apply_inner_glow":
        warnings.warn(
            "apply_inner_glow устарел — это alias для apply_glow (диспетчер). "
            "Используйте: from retouch.processing.glow import apply_glow",
            DeprecationWarning,
            stacklevel=2,
        )
        return apply_glow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
