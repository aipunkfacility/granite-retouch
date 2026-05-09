"""Stone Gamma — компенсация визуального потемнения на камне.

SOP 5.1: Gamma 0.8–0.9 поднимает тени для компенсации визуального
потемнения изображения на камне. В отличие от линейного brightness,
gamma-коррекция поднимает тени, не затрагивая белую точку.

Физика: полированный гранит темнит изображение из-за диффузного
отражения в кристаллах кварца и полевого шпата. Gamma < 1.0
компенсирует этот эффект, «растягивая» тени и средние тона.
"""

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def apply_stone_gamma(arr, gamma=0.88):
    """Применить gamma-коррекцию к массиву изображения.

    Gamma < 1.0 поднимает тени (осветление), gamma > 1.0 затемняет.
    Белая точка (255) остаётся на месте.

    Args:
        arr: numpy array (float32), значения 0-255
        gamma: показатель степени (0.8–0.9 по SOP для камня)

    Returns:
        numpy array: скорректированный массив в [0, 255]
    """
    if not HAS_NUMPY:
        return arr
    norm = arr / 255.0
    corrected = np.power(norm, gamma) * 255.0
    return np.clip(corrected, 0, 255)


def apply_stone_gamma_masked(arr, mask, gamma=0.88):
    """Применить gamma-коррекцию только внутри маски субъекта.

    Пиксели вне маски не меняются. Типичный вызов из пайплайна.

    Args:
        arr: numpy array (float32), значения 0-255
        mask: numpy bool array — True = субъект
        gamma: показатель степени (0.8–0.9 по SOP)

    Returns:
        numpy array: скорректированный массив
    """
    if not HAS_NUMPY:
        return arr
    corrected = apply_stone_gamma(arr, gamma)
    return np.where(mask, corrected, arr)
