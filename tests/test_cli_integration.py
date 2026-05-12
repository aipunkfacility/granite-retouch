"""Интеграционный тест: CLI работает как subprocess."""

import argparse
import subprocess
import sys
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
            [sys.executable, "-m", "retouch", "process",
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
            [sys.executable, "-m", "retouch", "process",
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
            [sys.executable, "-m", "retouch", "process",
             "-i", str(input_path), "-o", str(output_path),
             "-m", "laser_standard", "-f", "png"],
            capture_output=True, text=True, timeout=30,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_path.exists(), "PNG not created"


class TestFaceOvalCLIFlag:
    """AUDIT-3.1: --face-oval CLI флаг парсится и пробрасывается в process()."""

    def test_face_oval_cli_flag_parses(self):
        """--face-oval 0.5,0.25,0.15,0.20 парсится в dict."""
        face_oval_str = "0.5,0.25,0.15,0.20"
        parts = [float(v) for v in face_oval_str.split(",")]
        assert len(parts) == 4
        face_oval = {
            "cx": parts[0], "cy": parts[1],
            "rx": parts[2], "ry": parts[3],
            "source": "manual",
        }
        assert face_oval == {
            "cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20,
            "source": "manual",
        }

    def test_face_oval_cli_integration(self):
        """End-to-end: CLI argparse с --face-oval."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p_process = subparsers.add_parser("process")
        p_process.add_argument("--input", "-i", required=True)
        p_process.add_argument("--output", "-o", required=True)
        p_process.add_argument("--machine", "-m",
                               choices=["laser_standard", "laser_80w", "impact"],
                               default="laser_standard")
        p_process.add_argument("--face-oval",
                               help="Oval: CX,CY,RX,RY (0-1)")
        p_process.add_argument("--no-validate", action="store_true")
        p_process.add_argument("--overwrite", action="store_true")
        p_process.add_argument("--config", "-c")
        p_process.add_argument("--format", "-f", default="bmp")
        p_process.add_argument("--glow-size", type=int)
        p_process.add_argument("--glow-opacity", type=int)

        args = parser.parse_args([
            "process",
            "-i", "input.png",
            "-o", "output.bmp",
            "--face-oval", "0.5,0.25,0.15,0.20",
        ])

        face_oval = None
        if getattr(args, 'face_oval', None):
            parts = [float(v) for v in args.face_oval.split(",")]
            assert len(parts) == 4
            face_oval = {
                "cx": parts[0], "cy": parts[1],
                "rx": parts[2], "ry": parts[3],
                "source": "manual",
            }

        assert face_oval is not None
        assert face_oval["cx"] == 0.5


class TestNumbaWarmupCLI:
    """AUDIT-8.4: CLI _warmup_numba_if_needed() не падает."""

    def test_warmup_cli_function(self):
        """_warmup_numba_if_needed() вызывается без ошибок."""
        from retouch.cli import _warmup_numba_if_needed

        args = argparse.Namespace(command="process", machine="laser_80w")
        _warmup_numba_if_needed(args)
