import os
import sys
import argparse
import random
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageChops


# Defaults (used when config.yaml is not found or PyYAML is not installed)
DEFAULTS = {
    "processing": {
        "blue_threshold": 30,
        "min_blue_ratio": 0.15,
        "min_resolution": 512,
        "result_min_black_ratio": 0.25,
        "fringe_radius": 3,
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
        "headroom": 0.6,
        "horizontal_oversize": 0.2,
    },
}


class ValidationError(Exception):
    """Ошибка валидации входных данных или результата."""
    pass


def load_config(config_path=None):
    """Загрузить конфигурацию из config.yaml. Fallback на DEFAULTS."""
    if config_path is None:
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
                  f"Install: uv pip install PyYAML")
            return DEFAULTS
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print(f"Config loaded: {config_path}")
        return config

    return DEFAULTS


def validate_image_input(input_path, config=None):
    """Проверить, что входное изображение пригодно для обработки.

    Проверки:
    1. Файл существует
    2. Файл — изображение (Pillow может открыть)
    3. Разрешение >= min_resolution (default: 512x512)
    4. Формат RGBA (или конвертируемый)
    """
    if config is None:
        config = DEFAULTS

    proc = config.get("processing", DEFAULTS["processing"])
    min_res = proc.get("min_resolution", 512)

    if not os.path.isfile(input_path):
        raise ValidationError(f"Входной файл не найден: {input_path}")

    try:
        img = Image.open(input_path)
    except Exception as e:
        raise ValidationError(f"Не удалось открыть изображение: {e}")

    width, height = img.size
    if width < min_res or height < min_res:
        raise ValidationError(
            f"Разрешение {width}x{height} ниже минимума {min_res}x{min_res}. "
            f"Для качественной гравировки нужно изображение большего размера."
        )

    if img.mode not in ("RGBA", "RGB", "P", "L"):
        raise ValidationError(
            f"Неподдерживаемый режим изображения: {img.mode}. "
            f"Ожидается RGBA, RGB или палитровое изображение."
        )

    img.close()
    return True


def validate_blue_chromakey(img, threshold=30, min_blue_ratio=0.15):
    """Проверить, что изображение содержит синий хромакей (#0000FF).

    Использует numpy при наличии (быстрее), иначе fallback на Pillow.

    Args:
        img: PIL.Image в режиме RGBA
        threshold: минимальная разница B-R и B-G для классификации как «синий»
        min_blue_ratio: минимальная доля синих пикселей (0.0 - 1.0)

    Returns:
        float: доля синих пикселей

    Raises:
        ValidationError: если синий хромакей не обнаружен
    """
    if HAS_NUMPY:
        arr = np.array(img)  # H x W x 4
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        blue_mask = (b > r + threshold) & (b > g + threshold)
        ratio = float(blue_mask.sum()) / blue_mask.size
    else:
        data = list(img.getdata())
        total = len(data)
        blue_pixels = sum(1 for px in data if px[2] > px[0] + threshold and px[2] > px[1] + threshold)
        ratio = blue_pixels / total

    if ratio < min_blue_ratio:
        raise ValidationError(
            f"Синий хромакей не обнаружен (синих пикселей: {ratio:.1%}, "
            f"минимум: {min_blue_ratio:.0%}). "
            f"Ожидается изображение с фоном #0000FF."
        )

    return ratio


def validate_result_black_ratio(img, min_black_ratio=0.25):
    """Проверить, что результат содержит достаточно чёрного фона.

    Args:
        img: PIL.Image в режиме RGB (результат обработки)
        min_black_ratio: минимальная доля чёрных пикселей (value < 10)

    Returns:
        float: доля чёрных пикселей

    Raises:
        ValidationError: если чёрного фона слишком мало
    """
    if HAS_NUMPY:
        arr = np.array(img)  # H x W x 3
        black_mask = (arr[..., 0] < 10) & (arr[..., 1] < 10) & (arr[..., 2] < 10)
        ratio = float(black_mask.sum()) / black_mask.size
    else:
        data = list(img.getdata())
        total = len(data)
        black_pixels = sum(1 for r, g, b in data if r < 10 and g < 10 and b < 10)
        ratio = black_pixels / total

    if ratio < min_black_ratio:
        raise ValidationError(
            f"Недостаточно чёрного фона в результате ({ratio:.1%}, "
            f"минимум: {min_black_ratio:.0%}). "
            f"Возможно, хромакей не был удалён или виньетка не наложилась."
        )

    return ratio


def remove_blue_background(img, threshold=30, fringe_radius=3):
    """Удалить синий хромакей и убрать синие рефлексы (fringe) по краям.

    Использует numpy для скорости (~50x быстрее Pillow для 2048x2048).
    Fallback на Pillow при отсутствии numpy.

    Args:
        img: PIL.Image в режиме RGBA
        threshold: порог для определения синего хромакея
        fringe_radius: радиус расширения маски для fringe removal (px)

    Returns:
        tuple: (img_without_bg, subject_mask) — оба PIL.Image
    """
    if HAS_NUMPY:
        return _remove_blue_numpy(img, threshold, fringe_radius)
    else:
        return _remove_blue_pillow(img, threshold, fringe_radius)


def _remove_blue_numpy(img, threshold=30, fringe_radius=3):
    """numpy-реализация: удаление хромакея + fringe removal."""
    arr = np.array(img, dtype=np.float32)  # H x W x 4
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    # Строгая маска синего фона
    blue_mask = (b > r + threshold) & (b > g + threshold)

    # --- Fringe removal ---
    # Расширяем маску на fringe_radius пикселей для захвата переходной зоны
    if fringe_radius > 0:
        from scipy.ndimage import binary_dilation
        expanded_mask = binary_dilation(blue_mask, iterations=fringe_radius)
    else:
        expanded_mask = blue_mask

    # В переходной зоне (expanded_mask ∩ ¬blue_mask) гасим синий канал
    fringe_zone = expanded_mask & ~blue_mask

    # Мягкое гашение: чем сильнее пиксель «синий», тем сильнее гасим
    # Синий приводим к среднему из R и G (нейтральный серый)
    blue_strength = np.clip((b - np.maximum(r, g)) / (threshold * 2), 0, 1)
    fringe_factor = fringe_zone.astype(np.float32) * blue_strength

    # Гасим синий канал в переходной зоне
    arr[..., 2] = arr[..., 2] * (1 - fringe_factor) + np.maximum(r, g) * fringe_factor

    # Удаляем чистый синий фон
    arr[blue_mask] = [0, 0, 0, 0]

    # Субъект-маска
    subject_arr = (~blue_mask).astype(np.uint8) * 255

    img_result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    subject_mask = Image.fromarray(subject_arr, "L")

    return img_result, subject_mask


def _remove_blue_pillow(img, threshold=30, fringe_radius=3):
    """Pillow-fallback: удаление хромакея + упрощённый fringe removal."""
    width, height = img.size
    data = list(img.getdata())
    new_data = []
    mask_pixels = []

    for item in data:
        r, g, b, a = item
        if b > r + threshold and b > g + threshold:
            new_data.append((0, 0, 0, 0))
            mask_pixels.append(0)
        else:
            # Fringe: если синий чуть выше, чем R/G — приглушить
            if fringe_radius > 0 and b > r and b > g:
                # Мягкое гашение синего в переходной зоне
                blue_excess = min((b - max(r, g)) / (threshold * 2), 1.0)
                b_corrected = int(b * (1 - blue_excess) + max(r, g) * blue_excess)
                new_data.append((r, g, b_corrected, a))
            else:
                new_data.append(item)
            mask_pixels.append(255)

    img_result = Image.new("RGBA", (width, height))
    img_result.putdata(new_data)
    subject_mask = Image.new('L', (width, height))
    subject_mask.putdata(mask_pixels)

    return img_result, subject_mask


def check_face_brightness(img_gray, face_target, subject_mask):
    """Проверить и скорректировать яркость лица для ЧПУ.

    Для гравировки критична яркость лица:
    - Лазер: 230-245 (среднее пикселей лица в этой зоне)
    - Ударная: 220-235

    Если средняя яркость лица вне целевого диапазона —
    автоматически скорректировать brightness factor.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        face_target: [min, max] целевого диапазона яркости
        subject_mask: PIL.Image в режиме L (маска субъекта)

    Returns:
        PIL.Image: скорректированное grayscale-изображение
    """
    if HAS_NUMPY:
        arr = np.array(img_gray, dtype=np.float32)
        mask_arr = np.array(subject_mask)

        # Средняя яркость субъекта (лицо + одежда)
        subject_pixels = arr[mask_arr > 128]
        if len(subject_pixels) == 0:
            return img_gray

        avg_brightness = float(subject_pixels.mean())

        target_min, target_max = face_target
        target_mid = (target_min + target_max) / 2

        if avg_brightness < target_min or avg_brightness > target_max:
            # Корректировка: множитель, приводящий среднее к target_mid
            correction = target_mid / max(avg_brightness, 1)
            # Ограничиваем коррекцию чтобы не пересветить
            correction = max(0.85, min(1.25, correction))
            arr = np.clip(arr * correction, 0, 255).astype(np.uint8)
            corrected = Image.fromarray(arr, "L")
            print(f"Face brightness corrected: {avg_brightness:.0f} → "
                  f"{target_mid:.0f} (factor: {correction:.3f})")
            return corrected

        print(f"Face brightness OK: {avg_brightness:.0f} (target: {target_min}-{target_max})")
    else:
        # Pillow fallback
        from PIL import ImageStat
        stat = ImageStat.Stat(img_gray, mask=subject_mask)
        avg_brightness = stat.mean[0]

        target_min, target_max = face_target
        target_mid = (target_min + target_max) / 2

        if avg_brightness < target_min or avg_brightness > target_max:
            correction = target_mid / max(avg_brightness, 1)
            correction = max(0.85, min(1.25, correction))
            enhancer = ImageEnhance.Brightness(img_gray)
            corrected = enhancer.enhance(correction)
            print(f"Face brightness corrected: {avg_brightness:.0f} → "
                  f"{target_mid:.0f} (factor: {correction:.3f})")
            return corrected

        print(f"Face brightness OK: {avg_brightness:.0f} (target: {target_min}-{target_max})")

    return img_gray


def apply_retouch_processing(input_path, output_path, machine_type="laser",
                             glow_size_override=None, glow_opacity_override=None,
                             config=None):
    """Подготовка файла для гравировки: удаление хромакея, Inner Glow, виньетка.

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

    Raises:
        ValidationError: при проблемах с входными данными или результатом
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

    # ---- Step 1: Validate input ----
    validate_image_input(input_path, config)

    # ---- Step 2: Load image ----
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size
    print(f"Image loaded: {width}x{height}, mode: {img.mode}")
    if HAS_NUMPY:
        print(f"numpy: enabled (accelerated processing)")
    else:
        print(f"numpy: not installed (install: uv pip install numpy)")

    # ---- Step 3: Validate chromakey ----
    blue_ratio = validate_blue_chromakey(img, threshold=blue_threshold,
                                         min_blue_ratio=min_blue_ratio)
    print(f"Chromakey check passed: {blue_ratio:.1%} blue pixels (threshold: {min_blue_ratio:.0%})")

    # ---- Step 4: Remove Blue Background + Fringe Removal ----
    img, subject_mask = remove_blue_background(img, threshold=blue_threshold,
                                                fringe_radius=fringe_radius)
    print(f"Blue background removed (fringe_radius: {fringe_radius})")

    # ---- Step 5: Inner Glow (Contour Light) ----
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

    # ---- Step 6: Grayscale + Levels + Unsharp ----
    img_gray = img.convert("L")
    img_with_glow = Image.composite(Image.new('L', (width, height), 255), img_gray, glow_mask)

    # Levels (brightness from config)
    enhancer = ImageEnhance.Brightness(img_with_glow)
    img_leveled = enhancer.enhance(brightness_factor)

    # Unsharp Mask
    img_final = img_leveled.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=0))

    # ---- Step 7: Face brightness control ----
    face_target = machine_cfg.get("face_brightness_target", [230, 245])
    img_final = check_face_brightness(img_final, face_target, subject_mask)

    # ---- Step 8: Arch/Vignette Mask ----
    arch = Image.new('L', (width, height), 0)
    draw_arch = ImageDraw.Draw(arch)

    v_offset = height * vign_cfg.get("vertical_offset", 0.10)
    v_diameter = height * vign_cfg.get("vertical_diameter", 0.50)
    blur_radius = vign_cfg.get("blur_radius", 60)
    headroom = height * vign_cfg.get("headroom", 0.6)
    h_oversize = width * vign_cfg.get("horizontal_oversize", 0.2)

    arch_bottom_y = height - v_offset
    arch_top_y = arch_bottom_y - v_diameter - headroom

    draw_arch.ellipse(
        [-h_oversize, arch_top_y, width + h_oversize, arch_bottom_y],
        fill=255
    )
    arch_mask = arch.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Composite Final Image over black
    background = Image.new('RGB', (width, height), (0, 0, 0))
    background.paste(img_final, (0, 0), arch_mask)

    # ---- Step 9: Validate result ----
    black_ratio = validate_result_black_ratio(background, min_black_ratio=result_min_black)
    print(f"Result check passed: {black_ratio:.1%} black background")

    # ---- Step 10: Save ----
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Always save TIFF
    background.save(output_path, "TIFF")

    # Also save PNG alongside
    output_png = output_path.replace(".tiff", ".png").replace(".tif", ".png")
    if output_png == output_path:
        output_png = output_path + ".png"
    background.save(output_png, "PNG")

    print(f"Saved: {output_path}")
    print(f"Saved: {output_png}")
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
    parser.add_argument("--no-validate", action="store_true",
        help="Пропустить валидацию входного изображения и результата")
    args = parser.parse_args()

    config = load_config(args.config)

    try:
        if args.no_validate:
            if not os.path.isfile(args.input):
                parser.error(f"Входной файл не найден: {args.input}")
            config_noval = dict(config)
            proc_noval = dict(config.get("processing", {}))
            proc_noval["min_blue_ratio"] = 0.0
            proc_noval["min_resolution"] = 0
            proc_noval["result_min_black_ratio"] = 0.0
            config_noval["processing"] = proc_noval
            apply_retouch_processing(
                args.input, args.output,
                machine_type=args.machine,
                glow_size_override=args.glow_size,
                glow_opacity_override=args.glow_opacity,
                config=config_noval,
            )
        else:
            apply_retouch_processing(
                args.input, args.output,
                machine_type=args.machine,
                glow_size_override=args.glow_size,
                glow_opacity_override=args.glow_opacity,
                config=config,
            )
    except ValidationError as e:
        print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
