"""Сгенерировать synthetic test fixtures для dither regression."""

import numpy as np
from PIL import Image
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def _make_face_like():
    """Эллипс ~100 на равномерном фоне ~200."""
    arr = np.full((256, 256), 200, dtype=np.uint8)
    cy, cx = 128, 128
    y, x = np.ogrid[:256, :256]
    mask = ((x - cx) / 60) ** 2 + ((y - cy) / 80) ** 2 <= 1.0
    arr[mask] = 150
    return arr


def _make_high_contrast():
    """Чередующиеся полосы 0 и 255."""
    arr = np.zeros((256, 256), dtype=np.uint8)
    arr[:, ::32] = 255
    return arr


def generate_fixtures():
    """Создать 5 synthetic изображений 256x256 с разными тональными профилями."""
    fixtures = {
        "mid_gray.png": np.full((256, 256), 128, dtype=np.uint8),
        "gradient_h.png": np.tile(
            np.linspace(0, 255, 256, dtype=np.uint8), (256, 1)
        ),
        "gradient_v.png": np.tile(
            np.linspace(0, 255, 256, dtype=np.uint8).reshape(-1, 1), (1, 256)
        ),
        "face_like.png": _make_face_like(),
        "high_contrast.png": _make_high_contrast(),
    }
    for name, arr in fixtures.items():
        path = FIXTURES_DIR / name
        Image.fromarray(arr, mode="L").save(path)
        print(f"Created: {path}")


if __name__ == "__main__":
    generate_fixtures()
