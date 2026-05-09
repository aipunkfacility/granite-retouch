"""Тесты экспорта — дизеринг, upsampling, BMP."""

import os
import numpy as np
import pytest
from PIL import Image

from retouch.config import load_config


class TestStuckiDithering:
    """Stucki dithering для impact (SOP 4.1)."""

    def test_stucki_produces_1bit_output(self):
        """Stucki даёт 1-bit изображение."""
        from retouch.processing.export import stucki_dither
        img = Image.new("L", (100, 100), 128)
        result = stucki_dither(img)
        assert result.mode == "1"

    def test_stucki_preserves_tone(self):
        """Средняя плотность белых точек примерно равна input brightness."""
        from retouch.processing.export import stucki_dither
        img = Image.new("L", (200, 200), 128)
        result = stucki_dither(img)
        white_ratio = np.array(result, dtype=np.float32).mean()
        assert 0.40 < white_ratio < 0.60, \
            f"50% серый — примерно 50% белых точек, got {white_ratio:.2%}"

    def test_stucki_output_size_matches_input(self):
        """Размер результата = размер входа."""
        from retouch.processing.export import stucki_dither
        img = Image.new("L", (150, 200), 100)
        result = stucki_dither(img)
        assert result.size == (150, 200)


class TestJarvisDithering:
    """Jarvis dithering для laser_80w (SOP 4.1)."""

    def test_jarvis_produces_1bit_output(self):
        """Jarvis даёт 1-bit изображение."""
        from retouch.processing.export import jarvis_dither
        img = Image.new("L", (100, 100), 128)
        result = jarvis_dither(img)
        assert result.mode == "1"

    def test_jarvis_preserves_tone(self):
        """Средняя плотность белых точек примерно равна input brightness."""
        from retouch.processing.export import jarvis_dither
        img = Image.new("L", (200, 200), 128)
        result = jarvis_dither(img)
        white_ratio = np.array(result, dtype=np.float32).mean()
        assert 0.40 < white_ratio < 0.60, \
            f"50% серый — примерно 50% белых точек, got {white_ratio:.2%}"

    def test_jarvis_output_size_matches_input(self):
        """Размер результата = размер входа."""
        from retouch.processing.export import jarvis_dither
        img = Image.new("L", (150, 200), 100)
        result = jarvis_dither(img)
        assert result.size == (150, 200)


class TestDitherMethodConfig:
    """Выбор алгоритма дизеринга из конфига."""

    def test_impact_has_dither_method(self):
        """Impact: dither_method = stucki."""
        config = load_config()
        method = config["processing"]["impact"].get("dither_method", "")
        assert method == "stucki", f"impact dither_method должен быть stucki, got {method}"

    def test_laser_80w_has_dither_method(self):
        """Laser 80W: dither_method = jarvis."""
        config = load_config()
        method = config["processing"]["laser_80w"].get("dither_method", "")
        assert method == "jarvis", f"laser_80w dither_method должен быть jarvis, got {method}"

    def test_laser_standard_has_no_dither(self):
        """Laser standard: нет 1-bit дизеринга (8-bit BMP)."""
        config = load_config()
        method = config["processing"]["laser_standard"].get("dither_method", "none")
        assert method == "none", f"laser_standard не должен иметь dither, got {method}"


class TestDitherUpsampling:
    """2-4x upsampling перед дизерингом (SOP 5.2)."""

    def test_upsample_config_laser_80w(self):
        """Laser 80W: dither_upsample >= 2."""
        config = load_config()
        upsample = config["processing"]["laser_80w"].get("dither_upsample", 1)
        assert upsample >= 2, f"laser_80w dither_upsample должен быть >= 2, got {upsample}"

    def test_upsample_output_size_matches_input(self):
        """Результат upsampling+dither — того же размера что и вход."""
        from retouch.processing.export import dither_with_upsample
        img = Image.new("L", (100, 120), 128)
        result = dither_with_upsample(img, method="jarvis", upsample=2)
        assert result.size == (100, 120)

    def test_upsample_improves_quality_vs_no_upsample(self):
        """Upsampling даёт другой (лучший) результат чем без него."""
        from retouch.processing.export import jarvis_dither, dither_with_upsample
        img = Image.new("L", (100, 100), 128)
        result_no_upsample = jarvis_dither(img)
        result_with_upsample = dither_with_upsample(img, method="jarvis", upsample=2)
        arr1 = np.array(result_no_upsample).flatten()
        arr2 = np.array(result_with_upsample).flatten()
        assert not np.array_equal(arr1, arr2), \
            "Upsampling должен давать другой результат дизеринга"


class TestBMPValidation:
    """BMP post-save валидация."""

    def test_bmp_8bit_roundtrip(self, tmp_path):
        """BMP 8-bit: save -> reopen -> same size, mode L or P."""
        from retouch.processing.export import save_bmp_8bit

        img = Image.new("L", (256, 256), 128)
        output_path = str(tmp_path / "test.bmp")

        save_bmp_8bit(img, output_path)

        with Image.open(output_path) as reopened:
            assert reopened.size == (256, 256)
            assert reopened.mode in ("L", "P")

    def test_bmp_1bit_roundtrip(self, tmp_path):
        """BMP 1-bit: save -> reopen -> mode 1 or P."""
        from retouch.processing.export import save_bmp_1bit

        img = Image.new("L", (256, 256), 128)
        output_path = str(tmp_path / "test_1bit.bmp")

        save_bmp_1bit(img, output_path)

        with Image.open(output_path) as reopened:
            assert reopened.size == (256, 256)
            assert reopened.mode in ("1", "P")

    def test_export_creates_bmp_and_png(self, tmp_path):
        """export_result создаёт BMP + PNG."""
        from retouch.processing.export import export_result

        img = Image.new("RGB", (256, 256), (128, 128, 128))
        output_path = str(tmp_path / "output.bmp")

        result = export_result(img, output_path, machine_type="laser_standard")

        assert os.path.isfile(result)
        assert os.path.isfile(str(tmp_path / "output.png"))

    def test_floyd_steinberg_50_50(self):
        """Floyd-Steinberg: grayscale 128 — примерно 50/50 white/black."""
        from retouch.processing.export import floyd_steinberg_dither

        img = Image.new("L", (200, 200), 128)
        result = floyd_steinberg_dither(img)

        arr = np.array(result.convert("L"))
        white_pct = (arr > 128).sum() / arr.size * 100

        assert 35 < white_pct < 65, \
            f"При grayscale=128 Floyd-Steinberg даёт примерно 50% белого, got {white_pct:.1f}%"
