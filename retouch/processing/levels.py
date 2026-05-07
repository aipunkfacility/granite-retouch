"""Levels + Brightness + Unsharp Mask + контроль яркости лица."""

import logging

from PIL import Image, ImageEnhance, ImageFilter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


def apply_levels(img_gray, brightness_factor=None, analytics=None, machine_type=None, subject_mask=None):
    """Применить Levels (brightness adjustment).

    Поддерживает два режима:
    - Legacy: positional brightness_factor, analytics=None → простой brightness enhance.
    - Adaptive: analytics provided → фактор вычисляется из метрик и machine_type.

    Args:
        img_gray: PIL.Image в режиме L
        brightness_factor: множитель яркости (1.0 = нейтрально).
            Используется в legacy-режиме (когда analytics is None).
        analytics: dict от analyze_input() — если передан, включается
            адаптивный расчёт фактора (P2).
        machine_type: str — тип станка ('laser_standard', 'laser_80w', 'impact').
            Используется только вместе с analytics.
        subject_mask: PIL.Image в режиме L — маска субъекта.
            Когда передана, коррекция применяется только внутри маски (P6).

    Returns:
        PIL.Image: скорректированное изображение
    """
    # Определяем фактор яркости
    if analytics is not None:
        # P2: Адаптивный расчёт фактора
        factor = _adaptive_levels_factor(analytics, machine_type)
    elif brightness_factor is not None:
        # Legacy: явный фактор
        factor = brightness_factor
    else:
        # Default: нейтральный
        factor = 1.0

    # Применяем коррекцию
    if subject_mask is not None and HAS_NUMPY:
        # P6: Mask protection — коррекция только внутри маски
        mask_bool = np.array(subject_mask) > 128
        arr = np.array(img_gray, dtype=np.float32)
        corrected = arr * factor
        corrected = np.clip(corrected, 0, 255)
        result_arr = np.where(mask_bool, corrected, arr)
        return Image.fromarray(result_arr.astype(np.uint8), "L")
    else:
        # Без маски — глобальная коррекция (старое поведение)
        enhancer = ImageEnhance.Brightness(img_gray)
        return enhancer.enhance(factor)


def _adaptive_levels_factor(analytics: dict, machine_type: str | None) -> float:
    """P2: Рассчитать адаптивный фактор яркости на основе аналитики.

    Args:
        analytics: dict с метриками от analyze_input()
        machine_type: тип станка

    Returns:
        float: множитель яркости
    """
    target_pre_fb = {
        'laser_standard': 165,
        'laser_80w': 150,
        'impact': 135,
    }.get(machine_type, 155)

    median = analytics['median_brightness']
    factor = target_pre_fb / max(median, 1)
    factor = max(0.70, min(1.35, factor))

    # Защита от клиппинга
    if analytics['p90_brightness'] * factor > 250:
        safe_factor = 248 / max(analytics['p90_brightness'], 1)
        factor = min(factor, safe_factor)

    logger.info(
        "Adaptive levels: machine=%s, median=%.1f, target=%d, factor=%.3f",
        machine_type, median, target_pre_fb, factor,
    )
    return factor


def apply_unsharp_mask(img, radius=1.5, percent=120, threshold=0, subject_mask=None, analytics=None):
    """Применить Unsharp Mask.

    Args:
        img: PIL.Image (grayscale)
        radius: радиус размытия
        percent: сила эффекта
        threshold: порог
        subject_mask: PIL.Image в режиме L — маска субъекта.
            Когда передана, резкость применяется только внутри маски (P6).
        analytics: dict от analyze_input() — если передан, включается
            адаптивный расчёт percent (P5).

    Returns:
        PIL.Image: обработанное изображение
    """
    # P5: Адаптивный percent
    if analytics is not None:
        percent = _adaptive_unsharp_percent(analytics, percent)

    # Применяем Unsharp Mask
    sharpened = img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))

    # P6: Mask protection — резкость только внутри маски
    if subject_mask is not None and HAS_NUMPY:
        mask_bool = np.array(subject_mask) > 128
        orig_arr = np.array(img, dtype=np.float32)
        sharp_arr = np.array(sharpened, dtype=np.float32)
        result_arr = np.where(mask_bool, sharp_arr, orig_arr)
        return Image.fromarray(result_arr.astype(np.uint8), "L")

    return sharpened


def _adaptive_unsharp_percent(analytics: dict, default_percent: int) -> int:
    """P5: Рассчитать адаптивный percent для Unsharp Mask.

    Args:
        analytics: dict с метриками от analyze_input()
        default_percent: значение по умолчанию (используется как fallback)

    Returns:
        int: адаптированный percent
    """
    tonal_range = analytics.get('tonal_range', 80)
    input_class = analytics.get('input_class', 'bright')

    if input_class == 'overbright':
        percent = 80
    elif tonal_range < 40:
        percent = 150
    elif tonal_range > 80:
        percent = 120
    else:
        percent = 130

    logger.info(
        "Adaptive unsharp: class=%s, tonal_range=%.1f, percent=%d",
        input_class, tonal_range, percent,
    )
    return percent


def _shrink_mask(subject_mask, shrink_px):
    """Сжать маску — убрать крайние shrink_px пикселей.

    Это исключает зону inner glow из замера яркости лица.
    Glow-пиксели (255) на контуре завышают среднее.
    """
    if HAS_NUMPY:
        from scipy.ndimage import binary_erosion
        arr = np.array(subject_mask) > 128
        eroded = binary_erosion(arr, iterations=shrink_px)
        return Image.fromarray((eroded.astype(np.uint8) * 255), "L")
    else:
        # Pillow fallback: invert → blur → threshold
        from PIL import ImageOps
        inv = ImageOps.invert(subject_mask)
        blurred = inv.filter(ImageFilter.GaussianBlur(radius=shrink_px))
        # Threshold at 128 — pixels near edge become 0 in mask
        return blurred.point(lambda p: 255 if p < 128 else 0, "L")


def _curves_correction(arr, correction, highlight_start=200.0, mask=None,
                       target_ceiling=None):
    """Нелинейная коррекция: тени поднимаются, света не трогаются.

    Вместо linear brightness (всё × 1.15) — curves-подобная формула:
    - Тёмные пиксели (0) → полная коррекция
    - Средние пиксели (128) → 60% коррекции
    - Светлые пиксели (highlight_start+) → почти без коррекции

    Args:
        arr: numpy array (float32), значения 0-255
        correction: множитель коррекции (1.0 = нейтрально)
        highlight_start: значение (0-255), выше которого коррекция затухает
        mask: numpy bool array — коррекция применяется только внутри маски.
            Пиксели вне маски остаются без изменений. Если None — коррекция
            глобальная (старое поведение, НЕ рекомендуется).
        target_ceiling: float (0-255) — при осветлении (correction > 1.0) пиксели
            уже выше этого значения НЕ осветляются дальше. Предотвращает засвет
            уже ярких участков кожи. Если None — потолка нет.
    """
    # Нормализуем в 0-1
    norm = arr / 255.0

    # Weight: 1.0 для теней, 0.0 для светов
    h = highlight_start / 255.0
    weight = np.where(
        norm < h,
        1.0,
        np.clip(1.0 - (norm - h) / (1.0 - h), 0, 1)
    )

    # Линейная коррекция: pixel * correction
    linear = arr * correction

    # Разница: насколько линейная коррекция меняет пиксель
    delta = linear - arr

    # Применяем delta с weight — тени полностью, света минимально
    result = arr + delta * weight

    # Защита: при осветлении НЕ превышаем target_ceiling.
    # Пиксели уже у потолка — не осветляем, пиксели ниже — получают
    # ровно столько коррекции, чтобы не вылететь за потолок.
    # Это исправляет баг: пиксель 156 при factor=1.20 давал 187.2,
    # хотя target_ceiling=170. Теперь delta масштабируется так,
    # чтобы result = arr + delta * weight * ceiling_scale <= target_ceiling.
    if target_ceiling is not None and correction > 1.0:
        proposed_delta = delta * weight  # delta после curves-взвешивания
        max_allowed = np.maximum(target_ceiling - arr, 0)  # запас до потолка
        # Для положительных delta (осветление): масштабируем, чтобы не вылететь
        # Для отрицательных delta (затемнение): потолок не ограничивает
        ceiling_scale = np.where(
            proposed_delta > 0,
            np.minimum(max_allowed / np.maximum(proposed_delta, 0.001), 1.0),
            1.0,
        )
        result = arr + proposed_delta * ceiling_scale

    # Ограничение коррекции только внутри маски
    if mask is not None:
        result = np.where(mask, result, arr)

    return np.clip(result, 0, 255)


def check_face_brightness(img_gray, face_target, subject_mask, glow_size=0,
                          face_region_top=0.45, highlight_start=160):
    """Проверить и скорректировать яркость лица для ЧПУ.

    Использует НЕлинейную (curves) коррекцию:
    - Тёмные области (лицо) корректируются полностью
    - Светлые области (воротник) почти не трогаются
    - Коррекция применяется ТОЛЬКО внутри маски субъекта
    - Пиксели уже выше target_max не осветляются дальше (защита от засвета)

    Важное: перед осветлением проверяется РАСПРЕДЕЛЕНИЕ яркости лица.
    Если p75 уже >= target_max — осветление НЕ применяется, даже если
    медиана ниже target_min. Низкая медиана в таком случае означает,
    что в зоне лица много тёмных пикселей (волосы, тени), но кожа
    уже достаточно светлая и дополнительное осветление приведёт к засвету.

    Breaking Change: теперь возвращает кортеж (img, before, after, factor).
    Ранее возвращала только img.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        face_target: [min, max] целевого диапазона яркости
        subject_mask: PIL.Image в режиме L (маска субъекта)
        glow_size: размер inner glow — на столько пикселей сжимаем маску
        face_region_top: доля высоты изображения, в которой замеряется яркость.
            0.45 = верхние 45% картинки (голова без плеч).
        highlight_start: значение (0-255), выше которого коррекция затухает.
            Вынесено из хардкода 200 в параметр конфига.

    Returns:
        tuple: (img, before, after, factor) — скорректированное изображение,
               яркость до, яркость после, множитель коррекции.
    """
    # Сжать маску чтобы исключить glow-зону из замера
    if glow_size > 0:
        inner_mask_img = _shrink_mask(subject_mask, glow_size)
    else:
        inner_mask_img = subject_mask

    # Создаём маску субъекта (нужна в обеих ветках для P6.4)
    subject_mask_arr = np.array(subject_mask)
    full_subject_mask = subject_mask_arr > 128

    # Перцентили лица (p75, p90) — для защиты от засвета
    face_p75 = 0.0
    face_p90 = 0.0

    if HAS_NUMPY:
        arr = np.array(img_gray, dtype=np.float32)

        # A4: Правильная последовательность — сначала np.array от маски,
        # потом обрезка верхней части для зоны лица
        inner_mask_arr = np.array(inner_mask_img)

        # Ограничиваем зону замера верхней частью (лицо без плеч)
        # Используем сжатую маску (inner_mask_arr), чтобы исключить glow-пиксели
        h = img_gray.height
        cutoff = int(h * face_region_top)
        face_region = inner_mask_arr.copy()
        face_region[cutoff:, :] = 0  # Обнуляем нижнюю часть

        face_mask = face_region > 128
        if face_mask.sum() == 0:
            # fallback на полную сжатую маску (без обрезки по высоте)
            face_mask = inner_mask_arr > 128
        if face_mask.sum() == 0:
            # fallback на полную маску субъекта
            face_mask = full_subject_mask

        inner_pixels = arr[face_mask]
        if len(inner_pixels) == 0:
            # Нет пикселей субъекта — вернуть без изменений
            return img_gray, 0.0, 0.0, 1.0

        # МЕДИАНА вместо среднего: устойчива к тёмным выбросам
        # (волосы, тени на фоне зоны лица занижают среднее,
        #  но не влияют на медиану — она отражает реальную яркость кожи).
        avg_brightness = float(np.median(inner_pixels))

        # Перцентили для защиты от засвета: если яркие пиксели кожи
        # уже достигли целевого диапазона — осветлять нельзя, даже если
        # медиана низкая (она занижена волосами/тенями).
        face_p75 = float(np.percentile(inner_pixels, 75))
        face_p90 = float(np.percentile(inner_pixels, 90))
    else:
        from PIL import ImageStat
        stat = ImageStat.Stat(img_gray, mask=inner_mask_img)
        avg_brightness = stat.mean[0]

    target_min, target_max = face_target
    target_mid = (target_min + target_max) / 2

    logger.info(
        "Face brightness: %.1f (median), p75=%.1f, p90=%.1f → target %d-%d",
        avg_brightness, face_p75, face_p90, target_min, target_max,
    )

    if avg_brightness < target_min or avg_brightness > target_max:
        # ЗАЩИТА ОТ ЗАСВЕТА: если яркие пиксели кожи уже на месте,
        # низкая медиана — норма (волосы, тени), а не недодержка.
        if avg_brightness < target_min and HAS_NUMPY:
            if face_p75 >= target_max:
                # 75% перцентиль уже у потолка — кожа светлая, осветлять нельзя
                logger.info(
                    "Face brightening SKIPPED: median=%.1f < target_min=%d, "
                    "but p75=%.1f >= target_max=%d (skin already bright, "
                    "low median is from hair/shadows)",
                    avg_brightness, target_min, face_p75, target_max,
                )
                return img_gray, float(avg_brightness), float(avg_brightness), 1.0

            if face_p90 >= target_max - 15:
                # p90 приближается к потолку — ограничиваем коррекцию
                # чтобы не вытолкнуть яркие пиксели кожи в клиппинг
                gentle_cap = 1.08
                logger.info(
                    "Face brightening CAPPED at %.2f: p90=%.1f near target_max=%d",
                    gentle_cap, face_p90, target_max,
                )
                correction = target_mid / max(avg_brightness, 1)
                correction = max(0.70, min(gentle_cap, correction))
            else:
                correction = target_mid / max(avg_brightness, 1)
                correction = max(0.70, min(1.20, correction))
        else:
            correction = target_mid / max(avg_brightness, 1)
            correction = max(0.70, min(1.20, correction))

        if correction == 1.0:
            logger.info("Face brightness: correction resolved to 1.0, no change needed")
            return img_gray, float(avg_brightness), float(avg_brightness), 1.0

        if HAS_NUMPY:
            # Нелинейная коррекция: тени поднимаются, света нет.
            # ВАЖНО: передаём маску субъекта — коррекция только внутри неё,
            # и target_ceiling — пиксели уже выше target_max не осветляются.
            result_arr = _curves_correction(
                arr, correction,
                highlight_start=highlight_start,
                mask=full_subject_mask,
                target_ceiling=float(target_max) if correction > 1.0 else None,
            )
            result = Image.fromarray(result_arr.astype(np.uint8), "L")
        else:
            # Pillow fallback — простая линейная коррекция
            enhancer = ImageEnhance.Brightness(img_gray)
            result = enhancer.enhance(correction)
            # P6.4: ограничить коррекцию внутри маски субъекта.
            # Pillow не умеет mask-aware enhance, поэтому применяем
            # маску постфактум через numpy: вне маски — оригинал.
            if HAS_NUMPY:
                orig_arr = np.array(img_gray, dtype=np.float32)
                result_arr = np.array(result, dtype=np.float32)
                result_arr = np.where(full_subject_mask, result_arr, orig_arr)
                result = Image.fromarray(result_arr.astype(np.uint8), "L")
            else:
                logger.warning(
                    "Pillow-fallback: subject_mask передана, но numpy недоступен — "
                    "фон может загрязниться. Установите numpy: pip install numpy"
                )

        # Проверяем результат на маске лица (МЕДИАНА, не среднее!)
        if HAS_NUMPY:
            result_arr_check = np.array(result, dtype=np.float32)
            new_avg = float(np.median(result_arr_check[face_mask]))
            logger.info("Curves correction: factor=%.3f, %.1f → %.1f", correction, avg_brightness, new_avg)
        else:
            new_avg = target_mid
            logger.info("Linear correction: factor=%.3f, %.1f → %.1f", correction, avg_brightness, new_avg)

        return result, float(avg_brightness), float(new_avg), float(correction)

    logger.info("Face brightness OK, no correction needed")
    return img_gray, float(avg_brightness), float(avg_brightness), 1.0
