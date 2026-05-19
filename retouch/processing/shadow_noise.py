"""Shadow Noise — добавление шума в тёмные области субъекта для ударной гравировки."""

import logging

from PIL import Image

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


def add_shadow_noise(img_gray, subject_mask, noise_min=5, noise_max=15,
                     shadow_threshold=30, shadow_floor=0):
    """Добавить лёгкий шум в тёмные области субъекта (внутри маски).

    Для ударной гравировки: чисто чёрные области внутри субъекта (тени,
    тёмная одежда) вызывают «застой» иглы — она не бьёт, и на камне
    остаются необработанные зоны. Добавление шума (5–15) гарантирует,
    что игла будет работать по всей поверхности субъекта.

    ВАЖНО: шум добавляется ВНУТРИ маски субъекта, а не на фоне. Фон
    остаётся чисто чёрным (0) — это правильно для ЧПУ.

    Args:
        img_gray: PIL.Image в режиме L (grayscale)
        subject_mask: PIL.Image в режиме L (маска субъекта)
        noise_min: минимальное значение шума (по умолчанию 5)
        noise_max: максимальное значение шума (по умолчанию 15)
        shadow_threshold: порог яркости — пиксели субъекта ниже этого
            значения получают шум (по умолчанию 30)
        shadow_floor: минимальная яркость после shadow_floor в пайплайне.
            Шум ниже этого значения будет перезаписан shadow_floor,
            поэтому нижняя граница шума сдвигается до shadow_floor.

    Returns:
        PIL.Image: изображение с шумом в тёмных областях субъекта
    """
    if not HAS_NUMPY:
        logger.warning("add_shadow_noise: numpy недоступен — шум не добавлен")
        return img_gray

    arr = np.array(img_gray, dtype=np.float32)
    mask_bool = np.array(subject_mask) > 128

    # A.1 fix: шум в тёмных пикселях СУБЪЕКТА, не на фоне.
    # Тёмные области внутри маски = тени на лице, одежде — там игла
    # застревает. Фон (вне маски) остаётся чисто чёрным — это правильно.
    subject_dark = mask_bool & (arr < shadow_threshold)

    if subject_dark.sum() == 0:
        return img_gray

    # Генерируем шум в диапазоне [effective_min, noise_max]
    # effective_min = max(noise_min, shadow_floor): шум ниже shadow_floor
    # бессмысленен — shadow_floor в пайплайне перезапишет его до константы.
    effective_min = max(noise_min, shadow_floor) if shadow_floor > 0 else noise_min
    if effective_min >= noise_max:
        logger.warning(
            "Shadow noise: shadow_floor=%d >= noise_max=%d — шум не применяется",
            shadow_floor, noise_max,
        )
        return img_gray
    rng = np.random.default_rng(42)  # Фиксированный seed для воспроизводимости
    noise = rng.integers(effective_min, noise_max + 1, size=arr.shape).astype(np.float32)

    # Применяем шум только к тёмным пикселям субъекта
    # ВАЖНО: добавляем шум к пикселю (arr + noise), а НЕ заменяем (noise).
    # Замена уничтожает текстуру ткани — складки, градации пропадают.
    # Добавление сохраняет исходный градиент и гарантирует работу иглы.
    arr = np.where(subject_dark, arr + noise, arr)
    arr = np.clip(arr, 0, 255)

    logger.info(
        "Shadow noise: added %d-%d to %d dark subject pixels (threshold=%d, floor=%d)",
        effective_min, noise_max, subject_dark.sum(), shadow_threshold, shadow_floor,
    )
    return Image.fromarray(arr.astype(np.uint8))
