"""Сгенерировать reference .bmp для dither regression (v6.5).

Запускать после generate_fixtures.py. Референсы создаются export_result()
с текущим кодом — при регрессии dither выход не совпадёт.
"""

import tempfile
from pathlib import Path

from PIL import Image

from retouch.processing.output.export import export_result

FIXTURES_DIR = Path(__file__).parent


def _dither_fixture(name: str) -> None:
    """Загрузить fixture, применить dither, сохранить .bmp как reference."""
    src = FIXTURES_DIR / name
    img = Image.open(src).convert("L")

    ref_name = Path(name).stem + "_dither.bmp"
    ref_path = FIXTURES_DIR / ref_name

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.bmp"
        export_result(
            img, str(out),
            machine_type="laser_standard",
            fmt="bmp_1bit",
            export_mode="1bit",
            step_mm=0.300,
            dither_method_1bit="jarvis",
        )
        # Copy to fixtures
        with open(out, "rb") as src_f, open(ref_path, "wb") as dst_f:
            dst_f.write(src_f.read())

    print(f"Reference created: {ref_path}")


def generate_references():
    """Создать reference .bmp для всех 5 fixtures."""
    fixtures = [
        "mid_gray.png",
        "gradient_h.png",
        "gradient_v.png",
        "face_like.png",
        "high_contrast.png",
    ]
    for name in fixtures:
        _dither_fixture(name)


if __name__ == "__main__":
    generate_references()
