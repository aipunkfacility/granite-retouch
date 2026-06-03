#!/usr/bin/env python3
"""Метрики портрета для гравировки — сравнимо с выходом пайплайна.

Использование:
    python3 portrait-metrics.py <путь_к_изображению>

Поддерживает: PNG, JPEG, BMP, TIFF (любой формат PIL).
Автоматически переводит в Grayscale если нужно.

Зоны определяются приблизительно по геометрии (верх/центр = лицо).
Для точных зон нужна маска лица — см. комментарий в коде.
"""

import sys
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation


def analyze(filepath):
    img = Image.open(filepath)
    if img.mode != "L":
        img = img.convert("L")
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape

    print(f"Файл: {filepath}")
    print(f"Размер: {w}x{h}, режим: L")
    print()

    # Субъект: не-чёрные пиксели (порог 15 чтобы не ловить шум)
    subject = arr > 15
    bg = ~subject
    subject_px = arr[subject]

    if subject.sum() == 0:
        print("ОШИБКА: не найден субъект (все пиксели < 15)")
        sys.exit(1)

    # === ЗОНЫ (геометрическая аппроксимация) ===
    # Лицо: верхние 8-40% по высоте, центральные 60% по ширине
    face_top = int(h * 0.08)
    face_bottom = int(h * 0.40)
    face_left = int(w * 0.20)
    face_right = int(w * 0.80)

    face_region = np.zeros_like(subject)
    face_region[face_top:face_bottom, face_left:face_right] = True
    face_region = face_region & subject

    face_pixels = arr[face_region]
    if len(face_pixels) == 0:
        print("ОШИБКА: не найдены пиксели лица в ожидаемой зоне")
        sys.exit(1)

    face_median = np.median(face_pixels)

    # face_skin: освещённая кожа (выше median - 15)
    face_skin_mask = face_region & (arr > face_median - 15)
    # face_dark: тени, борода, брови (ниже median - 15)
    face_dark_mask = face_region & (arr <= face_median - 15)

    # Волосы: выше зоны лица
    hair_mask = np.zeros_like(subject)
    hair_mask[0:face_top, int(w * 0.15):int(w * 0.85)] = True
    hair_mask = hair_mask & subject

    # Одежда: ниже зоны лица
    clothes_mask = np.zeros_like(subject)
    clothes_mask[face_bottom:, :] = True
    clothes_mask = clothes_mask & subject

    # Блики: очень яркие пиксели субъекта
    highlights_mask = subject & (arr > 200)

    # === МЕТРИКИ ===
    zones = [
        ("face_skin", face_skin_mask),
        ("face_dark", face_dark_mask),
        ("clothes", clothes_mask),
        ("highlights", highlights_mask),
        ("hair", hair_mask),
    ]

    for name, mask in zones:
        px = arr[mask]
        if len(px) == 0:
            print(f"{name}: нет пикселей")
            continue
        px_int = px.astype(np.uint8)
        clipped = (px_int >= 255).sum()
        clipped_pct = 100.0 * clipped / len(px)

        print(f"  {name}:")
        print(f"    median:   {np.median(px_int):.0f}")
        print(f"    p10:      {np.percentile(px_int, 10):.0f}")
        print(f"    p90:      {np.percentile(px_int, 90):.0f}")
        print(f"    p95:      {np.percentile(px_int, 95):.0f}")
        print(f"    max:      {px_int.max()}")
        print(f"    variance: {px.var():.1f}")
        print(f"    clipped:  {clipped_pct:.2f}%")
        print()

    # === ИЕРАРХИЯ ===
    face_skin_px = arr[face_skin_mask]
    clothes_px = arr[clothes_mask]
    face_dark_px = arr[face_dark_mask]

    print("=" * 50)
    print("ИЕРАРХИЯ")
    print("=" * 50)

    if len(face_skin_px) > 0:
        fs_med = np.median(face_skin_px)
        print(f"  face_skin median:  {fs_med:.0f}")
    if len(clothes_px) > 0:
        cl_med = np.median(clothes_px)
        print(f"  clothes median:    {cl_med:.0f}")
        if len(face_skin_px) > 0:
            ratio = fs_med / cl_med if cl_med > 0 else float("inf")
            gap = fs_med - cl_med
            print(f"  ratio:             {ratio:.2f}x")
            print(f"  gap:               {gap:.0f} уровней")
            if gap > 30:
                print(f"  ✓ Лицо ярче одежды")
            else:
                print(f"  ✗ Лицо недостаточно ярче одежды (нужен gap > 30)")
    if len(face_dark_px) > 0:
        fd_med = np.median(face_dark_px)
        print(f"  face_dark median:  {fd_med:.0f}")
        if len(face_skin_px) > 0:
            skin_range = fs_med - fd_med
            print(f"  tonal range:       {skin_range:.0f}")

    # === КОНТУР (rim light) ===
    print()
    print("=" * 50)
    print("КОНТУР (rim light)")
    print("=" * 50)

    edge = binary_dilation(bg, iterations=8) & subject
    edge_px = arr[edge]
    if len(edge_px) > 0:
        print(f"  edge mean:   {edge_px.mean():.0f}")
        print(f"  edge median: {np.median(edge_px):.0f}")
        if edge_px.mean() > 30:
            print(f"  ✓ Контровой свет виден")
        else:
            print(f"  ✗ Контровой свет слабый (< 30)")

    # === ТЕНИ ===
    print()
    print("=" * 50)
    print("ТЕНИ")
    print("=" * 50)

    near_zero = (subject_px < 5).sum()
    near_zero_pct = 100.0 * near_zero / len(subject_px)
    print(f"  Пикселей < 5: {near_zero_pct:.2f}%")
    if near_zero_pct > 5:
        print(f"  ✗ Много чистого чёрного — нужен shadow noise")
    elif near_zero_pct > 1:
        print(f"  ⚠ Есть зоны около 0 — проверить нужны ли зацепки")
    else:
        print(f"  ✓ Тени не провалены в ноль")

    # === ЦЕЛЕВЫЕ ПРОВЕРКИ (impact) ===
    print()
    print("=" * 50)
    print("ЧЕКЛИСТ (impact)")
    print("=" * 50)

    checks = []

    if len(face_skin_px) > 0:
        fs_med = np.median(face_skin_px)
        fs_p95 = np.percentile(face_skin_px.astype(np.uint8), 95)
        fs_max = face_skin_px.astype(np.uint8).max()
        fs_clipped = (face_skin_px >= 245).sum()
        fs_clipped_pct = 100.0 * fs_clipped / len(face_skin_px)

        checks.append(("face_skin median 170–215", 170 <= fs_med <= 215, f"{fs_med:.0f}"))
        checks.append(("face_skin p95 < 240", fs_p95 < 240, f"{fs_p95:.0f}"))
        checks.append(("face_skin > 245: 0%", fs_clipped_pct < 0.5, f"{fs_clipped_pct:.2f}%"))
        checks.append(("face_skin variance > 100", face_skin_px.var() > 100, f"{face_skin_px.var():.1f}"))

    if len(highlights_mask) > 0:
        hl_max = arr[highlights_mask].astype(np.uint8).max()
        checks.append(("highlights max ≤ 250", hl_max <= 250, f"{hl_max}"))

    if len(face_skin_px) > 0 and len(clothes_px) > 0:
        gap = np.median(face_skin_px) - np.median(clothes_px)
        checks.append(("face > clothes на 30+", gap > 30, f"gap={gap:.0f}"))

    if len(edge_px) > 0:
        checks.append(("rim light edge > 30", edge_px.mean() > 30, f"{edge_px.mean():.0f}"))

    checks.append(("тени < 5: < 5%", near_zero_pct < 5, f"{near_zero_pct:.2f}%"))

    for name, passed, value in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {name} ({value})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Использование: python3 {sys.argv[0]} <путь_к_изображению>")
        sys.exit(1)
    analyze(sys.argv[1])
