"""Glow (Contour Light) — контурное свечение: inner и outer."""

from PIL import Image, ImageFilter, ImageChops

import numpy as np


def _calculate_glow_params(analytics: dict, machine_type: str,
                           machine_cfg: dict | None = None) -> tuple:
    """D.1: Рассчитать детерминированные параметры glow на основе аналитики.

    Рандомизация убрана — glow всегда одинаковый при одинаковых входных
    данных. Это гарантирует preview-export consistency (D.1).

    Все machine_type читают glow-диапазоны из machine_cfg с fallback на
    DEFAULTS. Результат — точка внутри диапазона, определяемая аналитикой:
    - laser_standard: позиция в диапазоне по tonal_range
    - laser_80w: midpoint диапазона (нет адаптивной логики)
    - impact: позиция в диапазоне по subject_separation

    Args:
        analytics: dict с метриками от analyze_input()
        machine_type: тип станка ('laser_standard', 'laser_80w', 'impact')
        machine_cfg: dict — параметры станка из config.yaml

    Returns:
        tuple: (glow_size, glow_opacity_percent) — размер и непрозрачность в %%
    """
    from retouch.config import DEFAULTS

    # Fallback на DEFAULTS если machine_cfg не передан или неполный
    fb = DEFAULTS["processing"].get(
        machine_type, DEFAULTS["processing"]["laser_standard"]
    )
    cfg = machine_cfg or {}
    glow_min = cfg.get('glow_size_min', fb['glow_size_min'])
    glow_max = cfg.get('glow_size_max', fb['glow_size_max'])
    opacity_min = cfg.get('glow_opacity_min', fb['glow_opacity_min'])
    opacity_max = cfg.get('glow_opacity_max', fb['glow_opacity_max'])

    if machine_type == 'impact':
        # Impact: больше separation → меньше glow (субъект хорошо отделён)
        separation = analytics.get('subject_separation', 150)
        if separation > 80:
            t = 0.25   # ближе к min диапазона
        elif separation > 40:
            t = 0.50   # середина диапазона
        else:
            t = 0.75   # ближе к max диапазона
    elif machine_type == 'laser_standard':
        # Laser standard: шире tonal_range → больше glow
        tonal_range = analytics.get('tonal_range', 100)
        if tonal_range > 120:
            t = 0.0    # узкий диапазон → минимальный glow
        elif tonal_range > 80:
            t = 0.5    # средний → midpoint
        else:
            t = 1.0    # широкий → максимальный glow
    else:
        # laser_80w: простой midpoint
        t = 0.5

    glow_size = int(glow_min + t * (glow_max - glow_min))
    glow_opacity = int(opacity_min + t * (opacity_max - opacity_min))
    return (glow_size, glow_opacity)


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
    glow_arr = np.array(glow_mask, dtype=np.float32)
    glow_arr = np.minimum(255.0, glow_arr * glow_opacity).astype(np.uint8)
    glow_mask = Image.fromarray(glow_arr)

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
    mask_arr = np.array(subject_mask) > 128

    # Сжимаем маску — внутренний край = разница
    # GaussianBlur вместо binary_erosion — изотропная, без лесеньки
    from scipy.ndimage import gaussian_filter
    iterations = max(1, glow_size / 2)  # BE-L4: float для точности
    inv = 1.0 - mask_arr.astype(np.float32)
    blurred = gaussian_filter(inv, sigma=iterations)
    shrunk = blurred < 0.5

    # Edge = внутренний край (контур внутри маски)
    edge = mask_arr & ~shrunk

    # Размываем край для плавного затухания к центру
    edge_img = Image.fromarray(edge.astype(np.uint8) * 255)
    edge_blurred = edge_img.filter(ImageFilter.GaussianBlur(glow_size / 2))  # BE-L4: float

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

    FIX: glow_size масштабируется пропорционально разрешению изображения.
    Конфигурационные значения glow_size заданы для эталонного разрешения
    REFERENCE_SIZE=768 (preview). На больших изображениях (экспорт 3000px+)
    glow_size умножается на scale=max(w,h)/768, чтобы относительный размер
    свечения оставался одинаковым. Без этого на экспорте glow почти невидим.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        subject_mask: PIL.Image в режиме L (маска субъекта, 255=субъект)
        machine_cfg: dict с параметрами станка из config.yaml
        glow_size_override: переопределить размер glow (px, БЕЗ масштабирования)
        glow_opacity_override: переопределить opacity glow (%%)
        analytics: dict от analyze_input() — если передан вместе с
            machine_type, параметры glow рассчитываются адаптивно (P3).
        machine_type: str — тип станка. Используется только вместе с analytics.
        glow_style: 'inner' | 'outer' | None (из конфига)

    Returns:
        PIL.Image: grayscale с Glow
        int: glow_size (px, УЖЕ масштабированный)
        float: glow_opacity (0.0–1.0)
    """
    # Эталонное разрешение — при котором конфигурационные glow_size корректны.
    # Это размер preview (768px по длинной стороне).
    REFERENCE_SIZE = 768

    # Определяем стиль glow
    style = glow_style or machine_cfg.get("glow_style", "outer")

    # Определяем параметры glow (в эталонных пикселях)
    if (analytics is not None and machine_type is not None
            and glow_size_override is None and glow_opacity_override is None):
        # P3: Адаптивные параметры из аналитики
        glow_size, glow_opacity_pct = _calculate_glow_params(analytics, machine_type, machine_cfg)
        glow_opacity = glow_opacity_pct / 100
    else:
        # D.1: Детерминированный fallback — midpoint диапазона из конфига.
        # Fallback-значения берём из DEFAULTS по machine_type, а не хардкодим
        # laser_standard (40, 80, 30, 40) — это давало неверные значения для
        # impact (10, 25, 60, 80) и laser_80w (15, 25, 10, 20).
        from retouch.config import DEFAULTS
        _fb = DEFAULTS["processing"].get(
            machine_type or "laser_standard",
            DEFAULTS["processing"]["laser_standard"],
        )
        glow_size_min = machine_cfg.get("glow_size_min", _fb["glow_size_min"])
        glow_size_max = machine_cfg.get("glow_size_max", _fb["glow_size_max"])
        glow_opacity_min = machine_cfg.get("glow_opacity_min", _fb["glow_opacity_min"])
        glow_opacity_max = machine_cfg.get("glow_opacity_max", _fb["glow_opacity_max"])

        glow_size = glow_size_override or int((glow_size_min + glow_size_max) / 2)  # BE-L4
        glow_opacity = (glow_opacity_override / 100) if glow_opacity_override else (
            (glow_opacity_min + glow_opacity_max) / 2 / 100  # BE-L4: float
        )

    # FIX: Масштабируем glow_size пропорционально разрешению.
    # glow_size в конфиге задан для REFERENCE_SIZE (768px).
    # На изображении 3000px: scale = 3000/768 ≈ 3.9, glow_size 60px → 234px.
    # glow_size_override уже учитывает масштаб (передаётся из preview,
    # который и так 768px), поэтому НЕ масштабируем override.
    if glow_size_override is None:
        img_long_side = max(img_gray.size)
        scale = img_long_side / REFERENCE_SIZE
        glow_size = max(1, int(glow_size * scale))

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

