"""Face Brightness Correction — нелинейная (curves) коррекция яркости лица."""

import logging

from PIL import Image, ImageEnhance, ImageFilter

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


def _shrink_mask(subject_mask, shrink_px):
    """Сжать маску — убрать крайние shrink_px пикселей.

    Это исключает зону inner glow из замера яркости лица.
    Glow-пиксели (255) на контуре завышают среднее.
    """
    if HAS_NUMPY:
        # GaussianBlur вместо binary_erosion — изотропная эрозия без лесенки.
        # binary_erosion с крестовым ядром даёт ступеньки на диагоналях.
        from scipy.ndimage import gaussian_filter
        arr_float = (np.array(subject_mask) > 128).astype(np.float32)
        # Эрозия = инвертировать → blur → порог → инвертировать
        inv = 1.0 - arr_float
        blurred = gaussian_filter(inv, sigma=shrink_px)
        # Порог erfc(1/√2)/2 ≈ 0.159: при sigma=shrink_px эрозия ровно на shrink_px пикселей
        eroded = blurred < 0.1587
        return Image.fromarray(eroded.astype(np.uint8) * 255)
    else:
        # Pillow fallback: invert → blur → threshold
        # GaussianBlur = изотропная эрозия (гладкая на диагоналях).
        # MinFilter давал ступеньки (квадратное ядро).
        from PIL import ImageOps, ImageFilter
        inv = ImageOps.invert(subject_mask)
        blurred = inv.filter(ImageFilter.GaussianBlur(radius=shrink_px))
        # Порог ≈40 (0.1587 * 255): при sigma=shrink_px эрозия ровно на shrink_px пикселей
        return blurred.point(lambda p, _t=40: 255 if p < _t else 0, "L")


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
        mask: numpy array (bool или float 0-1) — маска зоны коррекции.
            Если bool — бинарная маска (жёсткий край).
            Если float 0-1 — мягкая маска (градиентный переход, без видимого
            следа на лице). Если None — коррекция глобальная.
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
    if target_ceiling is not None and correction > 1.0:
        proposed_delta = delta * weight
        max_allowed = np.maximum(target_ceiling - arr, 0)
        ceiling_scale = np.where(
            proposed_delta > 0,
            np.minimum(max_allowed / np.maximum(proposed_delta, 0.001), 1.0),
            1.0,
        )
        result = arr + proposed_delta * ceiling_scale

    # Ограничение коррекции только внутри маски
    # Поддержка мягкой маски (float 0-1): альфа-блендинг вместо бинарного
    # переключателя. Градиентный переход = без видимого следа на лице.
    if mask is not None:
        if mask.dtype == bool:
            result = np.where(mask, result, arr)
        else:
            alpha = mask.astype(np.float32)
            result = arr + (result - arr) * alpha

    return np.clip(result, 0, 255)


def check_face_brightness(img_gray, face_target, subject_mask, glow_size=0,
                          face_region_top=0.45, highlight_start=160,
                          white_ceiling=None, face_mask_img=None):
    """Проверить и скорректировать яркость лица для ЧПУ.

    Использует НЕлинейную (curves) коррекцию:
    - Тёмные области (лицо) корректируются полностью
    - Светлые области (воротник) почти не трогаются
    - Коррекция применяется ТОЛЬКО внутри маски субъекта
    - Пиксели уже выше target_max не осветляются дальше (защита от засвета)
    - white_ceiling: жёсткий потолок яркости (240 для impact, 235 для laser_80w,
      250 для laser_standard). Значения выше ceiling обрезаются.

    Важное: перед осветлением проверяется РАСПРЕДЕЛЕНИЕ яркости лица.
    Если p75 уже >= target_max — осветление НЕ применяется, даже если
    медиана ниже target_min. Низкая медиана в таком случае означает,
    что в зоне лица много тёмных пикселей (волосы, тени), но кожа
    уже достаточно светлая и дополнительное осветление приведёт к засвету.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        face_target: [min, max] целевого диапазона яркости
        subject_mask: PIL.Image в режиме L (маска субъекта)
        glow_size: размер inner glow — на столько пикселей сжимаем маску
        face_region_top: доля высоты изображения, в которой замеряется яркость.
            0.45 = верхние 45% картинки (голова без плеч).
            **Игнорируется если передан face_mask_img.**
        highlight_start: значение (0-255), выше которого коррекция затухает.
        white_ceiling: int (0-255) — жёсткий потолок яркости.
        face_mask_img: PIL.Image в режиме L — маска зоны лица (из face_region.py).
            Если передана, используется для замера яркости вместо
            face_region_top. Приоритет выше face_region_top (C.3).

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

        # C.3: Приоритет face_mask_img над face_region_top
        if face_mask_img is not None:
            face_mask_arr = np.array(face_mask_img) > 128
            inner_mask_arr = np.array(inner_mask_img) > 128
            face_mask = face_mask_arr & inner_mask_arr
            if face_mask.sum() == 0:
                face_mask = face_mask_arr
            if face_mask.sum() == 0:
                face_mask = full_subject_mask
        else:
            # Legacy: ограничиваем зону замера верхней частью (лицо без плеч)
            inner_mask_arr = np.array(inner_mask_img)
            h = img_gray.height
            cutoff = int(h * face_region_top)
            face_region = inner_mask_arr.copy()
            face_region[cutoff:, :] = 0

            face_mask = face_region > 128
            if face_mask.sum() == 0:
                face_mask = inner_mask_arr > 128
            if face_mask.sum() == 0:
                face_mask = full_subject_mask

        inner_pixels = arr[face_mask]
        if len(inner_pixels) == 0:
            return img_gray, 0.0, 0.0, 1.0

        avg_brightness = float(np.median(inner_pixels))
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
        if avg_brightness < target_min and HAS_NUMPY:
            if face_p75 >= target_max:
                logger.info(
                    "Face brightening SKIPPED: median=%.1f < target_min=%d, "
                    "but p75=%.1f >= target_max=%d (skin already bright)",
                    avg_brightness, target_min, face_p75, target_max,
                )
                return img_gray, float(avg_brightness), float(avg_brightness), 1.0

            if face_p90 >= target_max - 15:
                gentle_cap = 1.08  # FIX #5: восстановлено (было 1.15)
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
            effective_ceiling = float(white_ceiling) if white_ceiling is not None and correction > 1.0 else (
                float(target_max) if correction > 1.0 else None
            )
            # Мягкая маска коррекции: GaussianBlur по маске лица → float 0-1.
            # Градиентный переход на краях = без видимого следа маски на лице.
            # Бинарная маска (bool) даёт резкий скачок яркости на границе.
            try:
                from scipy.ndimage import gaussian_filter as _gf
                feather_radius = max(5, glow_size // 4) if glow_size > 0 else 10
                soft_mask = _gf(face_mask.astype(np.float32), sigma=feather_radius)
                correction_mask_arr = np.clip(soft_mask, 0, 1)
                # Не позволяем мягкой маске «затекать» за границы субъекта
                correction_mask_arr = correction_mask_arr * full_subject_mask.astype(np.float32)
            except ImportError:
                correction_mask_arr = face_mask  # bool fallback

            result_arr = _curves_correction(
                arr, correction,
                highlight_start=highlight_start,
                mask=correction_mask_arr,
                target_ceiling=effective_ceiling,
            )
            if white_ceiling is not None:
                ceiling_mask = (correction_mask_arr > 0.5) & (result_arr > white_ceiling)
                result_arr = np.where(ceiling_mask, float(white_ceiling), result_arr)
            result = Image.fromarray(result_arr.astype(np.uint8))
        else:
            logger.warning(
                "check_face_brightness: numpy недоступен — коррекция применяется "
                "глобально (фон может загрязниться). Установите numpy: pip install numpy"
            )
            enhancer = ImageEnhance.Brightness(img_gray)
            result = enhancer.enhance(correction)

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
