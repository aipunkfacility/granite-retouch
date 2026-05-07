"""Интеграционный тест: CLI работает как subprocess."""

import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def test_cli_process_creates_output():
    """retouch process создаёт TIFF + PNG файлы."""
    # Создаём синтетическое изображение с хромакеем
    img = Image.new("RGBA", (512, 512), (0, 0, 255, 255))  # синий фон
    for x in range(200, 312):
        for y in range(200, 312):
            img.putpixel((x, y), (255, 255, 255, 255))

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.png"
        output_path = Path(tmp) / "output.tif"
        img.save(input_path)

        result = subprocess.run(
            ["python", "-m", "retouch", "process",
             "-i", str(input_path), "-o", str(output_path), "-m", "laser_standard"],
            capture_output=True, text=True, timeout=30,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_path.exists(), "TIFF not created"
        png_path = Path(tmp) / "output.png"
        assert png_path.exists(), "PNG not created"
