"""Интеграционный тест: CLI работает как subprocess."""

import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def test_cli_process_creates_bmp_output():
    """retouch process создаёт BMP + PNG файлы (по умолчанию)."""
    # Создаём синтетическое изображение с хромакеем
    img = Image.new("RGBA", (512, 512), (0, 0, 255, 255))  # синий фон
    for x in range(200, 312):
        for y in range(200, 312):
            img.putpixel((x, y), (255, 255, 255, 255))

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.png"
        output_path = Path(tmp) / "output.bmp"
        img.save(input_path)

        result = subprocess.run(
            ["python", "-m", "retouch", "process",
             "-i", str(input_path), "-o", str(output_path), "-m", "laser_standard"],
            capture_output=True, text=True, timeout=30,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_path.exists(), "BMP not created"
        png_path = Path(tmp) / "output.png"
        assert png_path.exists(), "PNG preview not created"


def test_cli_process_bmp_1bit_for_laser_80w():
    """retouch process -m laser_80w создаёт 1-bit BMP с дизерингом."""
    img = Image.new("RGBA", (512, 512), (0, 0, 255, 255))
    for x in range(200, 312):
        for y in range(200, 312):
            img.putpixel((x, y), (255, 255, 255, 255))

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.png"
        output_path = Path(tmp) / "output.bmp"
        img.save(input_path)

        result = subprocess.run(
            ["python", "-m", "retouch", "process",
             "-i", str(input_path), "-o", str(output_path), "-m", "laser_80w"],
            capture_output=True, text=True, timeout=30,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        # laser_80w: 1-bit BMP с дизерингом (файл меньше, чем 8-bit)
        assert output_path.exists(), "BMP not created for laser_80w"


def test_cli_process_png_format():
    """retouch process -f png создаёт только PNG."""
    img = Image.new("RGBA", (512, 512), (0, 0, 255, 255))
    for x in range(200, 312):
        for y in range(200, 312):
            img.putpixel((x, y), (255, 255, 255, 255))

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.png"
        output_path = Path(tmp) / "output.png"
        img.save(input_path)

        result = subprocess.run(
            ["python", "-m", "retouch", "process",
             "-i", str(input_path), "-o", str(output_path),
             "-m", "laser_standard", "-f", "png"],
            capture_output=True, text=True, timeout=30,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_path.exists(), "PNG not created"
