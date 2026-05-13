#!/usr/bin/env python3
"""Анализ яркости AI-генерации (ai.png) до пайплайна.

Измеряет метрики яркости кожи лица на сгенерированном изображении
для сравнения результатов A/B тестирования промптов.

Использование:
    python analyze_ai_brightness.py <ai.png> [--machine laser_80w] [--source source.jpg]

Метрики:
    skin_median   — медиана яркости кожи (цель: зависит от станка)
    skin_p90      — 90-й перцентиль кожи / блики
    skin_p10      — 10-й перцентиль кожи / тени
    skin_mean     — средняя яркость кожи
    tonal_range   — p90 - p10 (ширина тонального диапазона)
    max_non_eye   — максимальная яркость кожи без учёта белков глаз
    pct_above_235 — доля пикселей кожи выше 235 (потолок laser_80w)
    pct_above_240 — доля пикселей кожи выше 240 (потолок laser_standard/impact)
    full_median   — медиана по всему лицу (кожа + волосы)
    hair_median   — медиана по «волосам» (пиксели < skin_threshold в зоне лица)
    skin_pixels   — количество пикселей кожи
    hair_pixels   — количество пикселей волос
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Целевые диапазоны по типам станков
TARGETS = {
    "laser_standard": {
        "skin_median": (230, 245),
        "skin_p90": (230, 250),
        "skin_p10": (170, 200),
        "ceiling": 250,
    },
    "laser_80w": {
        "skin_median": (190, 210),
        "skin_p90": (200, 220),
        "skin_p10": (140, 170),
        "ceiling": 235,
    },
    "impact": {
        "skin_median": (200, 225),
        "skin_p90": (230, 240),
        "skin_p10": (160, 190),
        "ceiling": 240,
    },
}


def _detect_face_region_simple(img_gray):
    """Упрощённая детекция лица: верхние 45% изображения, внутри маски субъекта.

    Не использует dlib — работает на любой машине без зависимостей.
    Для точной маски можно передать source.jpg — тогда используется
    хромакей для отделения фона.
    """
    return None  # fallback — используем верхние 45%


def _extract_subject_mask(img):
    """Извлечь маску субъекта по хромакею (синий фон #0000FF).

    Работает для изображений с синим фоном (как в granite-retouch).
    """
    arr = np.array(img)
    if arr.ndim == 2:
        # Уже grayscale — предполагаем что 0 = фон
        return arr > 10

    # RGB/RGBA: синий канал доминирует
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    blue_strong = (b > 100) & (b > r * 1.5) & (b > g * 1.5)
    subject_mask = ~blue_strong
    return subject_mask


def analyze_image(image_path, machine_type="laser_80w", skin_threshold=100,
                  source_path=None):
    """Проанализировать AI-генерацию и вернуть метрики.

    Args:
        image_path: путь к ai.png
        machine_type: тип станка (для референсных таргетов)
        skin_threshold: порог кожа/волосы (default: 100)
        source_path: путь к source.jpg (опционально, для маски через хромакей)
    """
    img = Image.open(image_path)

    # Конвертация в grayscale
    if img.mode == "RGBA":
        # Убираем альфу, если есть
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.split()[3])
        img_gray = bg.convert("L")
    elif img.mode == "RGB":
        img_gray = img.convert("L")
    else:
        img_gray = img.convert("L")

    arr = np.array(img_gray, dtype=np.float32)

    # Маска субъекта: из AI-изображения через хромакей
    subject_mask = _extract_subject_mask(img)

    if subject_mask.sum() == 0:
        print("ОШИБКА: не удалось обнаружить субъект (маска пуста)")
        print("  Возможно, изображение не имеет синего хромакея")
        print("  Попробуйте --source source.jpg")
        sys.exit(1)

    # Зона лица: верхние 45% изображения (по умолчанию)
    h = arr.shape[0]
    cutoff = int(h * 0.45)
    face_zone = np.zeros_like(subject_mask)
    face_zone[:cutoff, :] = True
    face_mask = subject_mask & face_zone

    if face_mask.sum() == 0:
        # Fallback: всё изображение как лицо
        face_mask = subject_mask

    # Разделение кожи / волос
    face_skin_mask = face_mask & (arr >= skin_threshold)
    face_hair_mask = face_mask & (arr < skin_threshold)

    skin_pixels = arr[face_skin_mask]
    hair_pixels = arr[face_hair_mask]
    full_face_pixels = arr[face_mask]

    if len(skin_pixels) == 0:
        print("ОШИБКА: нет пикселей кожи (порог skin_threshold=%d слишком высокий)" % skin_threshold)
        sys.exit(1)

    # --- Вычисление метрик ---
    metrics = {}
    metrics["skin_median"] = float(np.median(skin_pixels))
    metrics["skin_mean"] = float(np.mean(skin_pixels))
    metrics["skin_p90"] = float(np.percentile(skin_pixels, 90))
    metrics["skin_p75"] = float(np.percentile(skin_pixels, 75))
    metrics["skin_p50"] = float(np.median(skin_pixels))
    metrics["skin_p25"] = float(np.percentile(skin_pixels, 25))
    metrics["skin_p10"] = float(np.percentile(skin_pixels, 10))
    metrics["skin_min"] = float(np.min(skin_pixels))
    metrics["skin_max"] = float(np.max(skin_pixels))
    metrics["tonal_range"] = metrics["skin_p90"] - metrics["skin_p10"]
    metrics["max_non_eye"] = float(np.max(skin_pixels))  # грубо — без детекции глаз
    metrics["pct_above_235"] = float(np.sum(skin_pixels > 235) / len(skin_pixels) * 100)
    metrics["pct_above_240"] = float(np.sum(skin_pixels > 240) / len(skin_pixels) * 100)
    metrics["pct_above_250"] = float(np.sum(skin_pixels > 250) / len(skin_pixels) * 100)

    metrics["full_median"] = float(np.median(full_face_pixels))
    metrics["skin_pixels"] = len(skin_pixels)
    metrics["hair_pixels"] = len(hair_pixels)
    metrics["skin_ratio"] = len(skin_pixels) / (len(skin_pixels) + len(hair_pixels)) * 100

    if len(hair_pixels) > 0:
        metrics["hair_median"] = float(np.median(hair_pixels))
    else:
        metrics["hair_median"] = 0.0

    metrics["image_size"] = "%dx%d" % (arr.shape[1], arr.shape[0])
    metrics["machine_type"] = machine_type
    metrics["skin_threshold"] = skin_threshold

    return metrics


def print_report(metrics):
    """Вывести отчёт в читаемом формате."""
    mt = metrics["machine_type"]
    targets = TARGETS.get(mt, {})

    print("=" * 60)
    print("  АНАЛИЗ ЯРКОСТИ AI-ГЕНЕРАЦИИ")
    print("=" * 60)
    print(f"  Изображение:    {metrics.get('image_path', '?')}")
    print(f"  Размер:         {metrics['image_size']}")
    print(f"  Тип станка:     {mt}")
    print(f"  skin_threshold: {metrics['skin_threshold']}")
    print()

    # --- Основные метрики с оценкой ---
    print("  МЕТРИКА              ЗНАЧЕНИЕ    ЦЕЛЕВОЙ ДИАПАЗОН    СТАТУС")
    print("  " + "-" * 56)

    def _status(value, target_range):
        if not target_range:
            return "?"
        lo, hi = target_range
        if lo <= value <= hi:
            return "OK"
        elif value < lo:
            diff = lo - value
            return "LOW (-%d)" % diff
        else:
            diff = value - hi
            return "HIGH (+%d)" % diff

    rows = [
        ("skin_median",   metrics["skin_median"],   targets.get("skin_median")),
        ("skin_p90",      metrics["skin_p90"],      targets.get("skin_p90")),
        ("skin_p10",      metrics["skin_p10"],      targets.get("skin_p10")),
        ("tonal_range",   metrics["tonal_range"],   None),
        ("max_non_eye",   metrics["max_non_eye"],   None),
    ]

    for name, value, target in rows:
        if target:
            lo, hi = target
            target_str = "%d-%d" % (lo, hi)
        else:
            target_str = "—"
        status = _status(value, target) if target else ""
        print(f"  {name:20s}  {value:8.1f}    {target_str:20s}  {status}")

    print()

    # --- Дополнительные метрики ---
    print("  ДОПОЛНИТЕЛЬНО:")
    print(f"    skin_mean:        {metrics['skin_mean']:.1f}")
    print(f"    skin_p75:         {metrics['skin_p75']:.1f}")
    print(f"    skin_p25:         {metrics['skin_p25']:.1f}")
    print(f"    skin_min:         {metrics['skin_min']:.1f}")
    print(f"    skin_max:         {metrics['skin_max']:.1f}")
    print(f"    full_median:      {metrics['full_median']:.1f}  (кожа + волосы)")
    print(f"    hair_median:      {metrics['hair_median']:.1f}  (пиксели < %d)" % metrics["skin_threshold"])
    print(f"    skin/hair ratio:  {metrics['skin_ratio']:.1f}% / {100-metrics['skin_ratio']:.1f}%")
    print(f"    skin pixels:      {metrics['skin_pixels']}")
    print(f"    hair pixels:      {metrics['hair_pixels']}")
    print()

    # --- Потолок яркости ---
    ceiling = targets.get("ceiling", 240)
    print("  ПОТОЛОК ЯРКОСТИ (ceiling=%d):" % ceiling)
    print(f"    > 235:  {metrics['pct_above_235']:.3f}%")
    print(f"    > 240:  {metrics['pct_above_240']:.3f}%")
    print(f"    > 250:  {metrics['pct_above_250']:.3f}%")

    if metrics["pct_above_235"] > 1.0:
        print(f"    ⚠  {metrics['pct_above_235']:.1f}% кожи выше 235 — риск пережога для laser_80w")
    if metrics["pct_above_240"] > 1.0:
        print(f"    ⚠  {metrics['pct_above_240']:.1f}% кожи выше 240 — риск пережога для laser_standard/impact")

    print()
    print("=" * 60)


def print_csv_header():
    """Вывести CSV-заголовок для сравнительной таблицы."""
    fields = [
        "variant", "image", "machine_type",
        "skin_median", "skin_p90", "skin_p10", "tonal_range",
        "full_median", "hair_median",
        "pct_above_235", "pct_above_240",
        "max_non_eye",
    ]
    print(",".join(fields))


def print_csv_row(metrics, variant="A"):
    """Вывести одну строку CSV для сравнительной таблицы."""
    fields = [
        variant,
        metrics.get("image_path", "?"),
        metrics["machine_type"],
        "%.1f" % metrics["skin_median"],
        "%.1f" % metrics["skin_p90"],
        "%.1f" % metrics["skin_p10"],
        "%.1f" % metrics["tonal_range"],
        "%.1f" % metrics["full_median"],
        "%.1f" % metrics["hair_median"],
        "%.3f" % metrics["pct_above_235"],
        "%.3f" % metrics["pct_above_240"],
        "%.1f" % metrics["max_non_eye"],
    ]
    print(",".join(fields))


def main():
    parser = argparse.ArgumentParser(
        description="Анализ яркости AI-генерации для A/B тестирования промптов",
    )
    parser.add_argument("image", help="Путь к ai.png (или несколько через пробел)")
    parser.add_argument("--machine", default="laser_80w",
                        choices=["laser_standard", "laser_80w", "impact"],
                        help="Тип станка для референсных таргетов (default: laser_80w)")
    parser.add_argument("--skin-threshold", type=int, default=100,
                        help="Порог кожа/волосы (default: 100)")
    parser.add_argument("--source", default=None,
                        help="Путь к source.jpg для маски через хромакей")
    parser.add_argument("--csv", action="store_true",
                        help="Вывести CSV для сравнительной таблицы")
    parser.add_argument("--variants", default=None,
                        help="Метки вариантов через запятую (напр. A,B,C) для CSV")

    args = parser.parse_args()

    # Поддержка нескольких файлов
    images = args.image.split() if " " in args.image else [args.image]
    variants = args.variants.split(",") if args.variants else [chr(65 + i) for i in range(len(images))]

    if len(variants) < len(images):
        variants.extend([chr(65 + i) for i in range(len(variants), len(images))])

    all_metrics = []

    for i, img_path in enumerate(images):
        path = Path(img_path)
        if not path.exists():
            print(f"ОШИБКА: файл не найден: {img_path}", file=sys.stderr)
            sys.exit(1)

        metrics = analyze_image(
            img_path,
            machine_type=args.machine,
            skin_threshold=args.skin_threshold,
            source_path=args.source,
        )
        metrics["image_path"] = str(path)
        all_metrics.append(metrics)

        if not args.csv:
            print_report(metrics)

    if args.csv:
        print_csv_header()
        for i, m in enumerate(all_metrics):
            print_csv_row(m, variant=variants[i])


if __name__ == "__main__":
    main()
