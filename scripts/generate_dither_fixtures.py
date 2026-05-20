"""Generate dither regression test fixtures."""
import os
import numpy as np
from PIL import Image

from retouch.processing.output.export import export_result

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "dither")


def create_fixtures():
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    fixtures = {
        "mid_gray": np.full((128, 128), 128, dtype=np.uint8),
        "gradient_h": np.tile(np.linspace(0, 255, 128, dtype=np.uint8), (128, 1)),
        "gradient_v": np.tile(np.linspace(0, 255, 128, dtype=np.uint8).reshape(-1, 1), (1, 128)),
        "face_like": _create_face_like(),
        "high_contrast": _create_high_contrast(),
    }

    for name, arr in fixtures.items():
        img = Image.fromarray(arr, mode="L")
        png_path = os.path.join(FIXTURES_DIR, f"{name}.png")
        img.save(png_path)
        print(f"Created {png_path}")

        bmp_path = os.path.join(FIXTURES_DIR, f"{name}_dither.bmp")
        export_result(
            img, bmp_path,
            machine_type="laser_standard",
            fmt="bmp_1bit",
            export_mode="1bit",
            step_mm=0.300,
            dither_method_1bit="jarvis",
        )
        print(f"Created {bmp_path}")


def _create_face_like():
    """Synthetic face-like image: oval of mid-gray on dark background."""
    arr = np.full((128, 128), 40, dtype=np.uint8)
    cy, cx = 64, 64
    for y in range(128):
        for x in range(128):
            dist = ((x - cx) / 35) ** 2 + ((y - cy) / 45) ** 2
            if dist < 1.0:
                arr[y, x] = 160
    return arr


def _create_high_contrast():
    """High contrast: black and white stripes."""
    arr = np.zeros((128, 128), dtype=np.uint8)
    arr[:, :32] = 255
    arr[:, 64:96] = 255
    arr[64:, 32:64] = 200
    return arr


if __name__ == "__main__":
    create_fixtures()
    print("All fixtures generated.")
