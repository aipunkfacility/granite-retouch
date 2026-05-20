import inspect
import numpy as np
import pytest
from PIL import Image
from retouch.processing.correction.shadow_noise import add_shadow_noise
from retouch.processing.correction.rolloff import soft_rolloff_masked
from retouch.processing.correction.unsharp import apply_unsharp_mask


@pytest.mark.parametrize("noise_min,noise_max,shadow_floor,exp_min,exp_max", [
    (5, 15, 8,  8, 15),   # impact defaults: effective_min=max(5,8)=8
    (5, 15, 0,  5, 15),   # без floor
    (10, 20, 8, 10, 20),  # расширенный диапазон
    (5, 15, 20, 20, 15),  # floor > noise_max → шум не применяется (return img)
])
def test_shadow_noise_range(noise_min, noise_max, shadow_floor, exp_min, exp_max):
    img = Image.new("L", (50, 50), 0)
    mask = Image.new("L", (50, 50), 255)
    result = add_shadow_noise(
        img, mask,
        noise_min=noise_min, noise_max=noise_max,
        shadow_threshold=30, shadow_floor=shadow_floor,
    )
    if shadow_floor >= noise_max:
        # Шум не применяется — изображение не изменено
        assert np.array_equal(np.array(result), np.array(img))
        return
    arr = np.array(result)
    dark = arr[arr < 30]
    assert len(dark) > 0
    assert int(dark.min()) >= exp_min
    assert int(dark.max()) <= exp_max


def test_shadow_noise_mask_protection():
    """Пиксели ВНЕ маски не должны изменяться (фон остаётся чёрным)."""
    img = Image.new("L", (100, 100), 0)
    # Только левая половина — субъект
    mask = Image.new("L", (100, 100), 0)
    import PIL.ImageDraw as ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.rectangle([0, 0, 49, 99], fill=255)

    result = add_shadow_noise(img, mask, noise_min=5, noise_max=15,
                              shadow_threshold=30, shadow_floor=0)
    arr = np.array(result)

    # Правая половина (вне маски) — должна остаться 0
    right_half = arr[:, 50:]
    assert (right_half == 0).all(), "Фон (вне маски) изменён — нарушена маска субъекта"

    # Левая половина (субъект) — должна получить шум
    left_half = arr[:, :50]
    assert (left_half > 0).any(), "Субъект не получил шум"


# --- Regression tests: soft knee (pipeline-refactor-plan Stage 0) ---


def test_soft_knee_values_above_knee_are_compressed():
    """Values above knee must be compressed below ceiling."""
    arr = np.full((100, 100), 250, dtype=np.float32)
    mask = np.ones((100, 100), dtype=bool)
    result = soft_rolloff_masked(arr, mask, knee=225, ceiling=250, compression=0.35)
    assert result.max() < 250, "values above knee must be compressed below ceiling"


def test_soft_knee_no_hard_plateau():
    """Градация выше knee должна сохраняться, а не схлопываться в плато."""
    arr = np.tile(np.arange(200, 256, dtype=np.float32), (100, 1))
    mask = np.ones((100, 56), dtype=bool)
    result = soft_rolloff_masked(arr, mask, knee=225, ceiling=250, compression=0.35)
    unique = len(np.unique(result[mask].astype(np.uint8)))
    assert unique > 10, "soft knee must preserve gradation, not produce plateau"


def test_soft_knee_chained_indexing_writes_back():
    """Regression: verify arr[mask][over] = val pattern is not used (writes to copy)."""
    source = inspect.getsource(soft_rolloff_masked)
    assert "arr[" not in source or "arr[mask_bool] = " in source
    assert "][over]" not in source, "chained indexing must not exist"


# --- Regression tests: unsharp clamp (pipeline-refactor-plan Stage 0) ---


def test_unsharp_no_hard_ceiling_plateau():
    """Unsharp не должен создавать плоское плато (hard clamp удалён)."""
    rng = np.random.RandomState(42)
    arr = np.zeros((100, 100), dtype=np.uint8)
    # Прямоугольник с синусоидой + шумом (вариации яркости)
    x = np.linspace(200, 255, 50)
    sine = (np.sin(np.linspace(0, 4 * np.pi, 50)) * 10 + 225).astype(np.uint8)
    texture = sine[np.newaxis, :] + rng.randint(-3, 4, (50, 50)).astype(np.int16)
    arr[25:75, 25:75] = np.clip(texture, 200, 255).astype(np.uint8)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[25:75, 25:75] = 255

    result = apply_unsharp_mask(
        Image.fromarray(arr), subject_mask=Image.fromarray(mask),
        threshold=0, percent=120,
    )
    result_arr = np.array(result)
    unique = len(np.unique(result_arr[mask > 128]))
    assert unique > 10, "unsharp should not produce flat plateau"


def test_unsharp_preserves_variance_above_knee():
    """Unsharp не должен уничтожать variance в светах (больше нет hard clamp)."""
    rng = np.random.RandomState(42)
    arr = np.zeros((100, 100), dtype=np.uint8)
    # Зона с высокой яркостью и variance
    zone = rng.randint(210, 251, (40, 40)).astype(np.uint8)
    arr[30:70, 30:70] = zone
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[30:70, 30:70] = 255

    var_before = float(np.var(arr[30:70, 30:70].astype(np.float32)))
    result = apply_unsharp_mask(
        Image.fromarray(arr), subject_mask=Image.fromarray(mask),
        threshold=0, percent=120,
    )
    result_arr = np.array(result)
    var_after = float(np.var(result_arr[30:70, 30:70].astype(np.float32)))
    # Unsharp увеличивает variance (повышает резкость)
    assert var_after >= var_before * 0.8, "unsharp must not destroy variance"
