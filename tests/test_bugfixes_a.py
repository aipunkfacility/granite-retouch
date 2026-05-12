import numpy as np
import pytest
from PIL import Image
from retouch.processing.shadow_noise import add_shadow_noise


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
