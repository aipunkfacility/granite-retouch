"""Общие утилиты для работы с масками субъекта.

Выделены из levels.py, unsharp.py, pipeline.py чтобы убрать дублирование
логики «применить только внутри маски».
"""

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def apply_masked(original_arr, modified_arr, subject_mask):
    """Применить modified_arr только внутри маски субъекта.

    Пиксели внутри маски (subject_mask > 128) = modified_arr.
    Пиксели вне маски = original_arr (не трогаются).

    Args:
        original_arr: numpy array — оригинальные значения
        modified_arr: numpy array — модифицированные значения
        subject_mask: PIL.Image L — маска субъекта (255=субъект)

    Returns:
        numpy array: результат с масочным ограничением
    """
    if not HAS_NUMPY:
        return modified_arr  # fallback — применять везде
    mask_bool = np.array(subject_mask) > 128
    return np.where(mask_bool, modified_arr, original_arr)


def clamp_masked(arr, subject_mask, vmin=None, vmax=None):
    """Ограничить значения внутри маски диапазоном [vmin, vmax].

    Пиксели вне маски не трогаются. Типичный use case:
    - shadow_floor: vmin=8, vmax=None
    - white_ceiling: vmin=None, vmax=200

    Args:
        arr: numpy array (float32 или uint8)
        subject_mask: PIL.Image L — маска субъекта (255=субъект)
        vmin: минимальное значение (или None)
        vmax: максимальное значение (или None)

    Returns:
        numpy array: ограниченный массив
    """
    if not HAS_NUMPY:
        return arr
    mask_bool = np.array(subject_mask) > 128
    result = arr.copy()
    if vmin is not None:
        result = np.where(mask_bool, np.maximum(result, vmin), result)
    if vmax is not None:
        result = np.where(mask_bool, np.minimum(result, vmax), result)
    return result
