"""Тесты Фазы 4 — Расширение экспорта (FIX #9, #10).

FIX #9: Stucki и Jarvis dithering (SOP 4.1)
FIX #10: Upsampling перед дизерингом (SOP 5.2)
"""

import numpy as np
import pytest
from PIL import Image

from retouch.config import load_config


class TestStuckiDithering:
    """FIX #9: Stucki dithering для impact (SOP 4.1)."""

    def test_stucki_produces_1bit_output(self):
        """Stucki даёт 1-bit изображение."""
        from retouch.processing.export import stucki_dither
        img = Image.new("L", (100, 100), 128)
        result = stucki_dither(img)
        assert result.mode == "1"

    def test_stucki_preserves_tone(self):
        """Средняя плотность белых точек ≈ input brightness."""
        from retouch.processing.export import stucki_dither
        img = Image.new("L", (200, 200), 128)
        result = stucki_dither(img)
        # PIL mode '1': 0=black, 255=white, но np.array даёт 0 и 1
        white_ratio = np.array(result, dtype=np.float32).mean()
        assert 0.40 < white_ratio < 0.60, \
            f"50% серый → ~50% белых точек, got {white_ratio:.2%}"

    def test_stucki_output_size_matches_input(self):
        """Размер результата = размер входа."""
        from retouch.processing.export import stucki_dither
        img = Image.new("L", (150, 200), 100)
        result = stucki_dither(img)
        assert result.size == (150, 200)


class TestJarvisDithering:
    """FIX #9: Jarvis dithering для laser_80w (SOP 4.1)."""

    def test_jarvis_produces_1bit_output(self):
        """Jarvis даёт 1-bit изображение."""
        from retouch.processing.export import jarvis_dither
        img = Image.new("L", (100, 100), 128)
        result = jarvis_dither(img)
        assert result.mode == "1"

    def test_jarvis_preserves_tone(self):
        """Средняя плотность белых точек ≈ input brightness."""
        from retouch.processing.export import jarvis_dither
        img = Image.new("L", (200, 200), 128)
        result = jarvis_dither(img)
        white_ratio = np.array(result, dtype=np.float32).mean()
        assert 0.40 < white_ratio < 0.60, \
            f"50% серый → ~50% белых точек, got {white_ratio:.2%}"

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
    """FIX #10: 2-4x upsampling перед дизерингом (SOP 5.2)."""

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
        # Результаты должны отличаться (upsampling меняет структуру дизеринга)
        arr1 = np.array(result_no_upsample).flatten()
        arr2 = np.array(result_with_upsample).flatten()
        # Хотя бы некоторые пиксели отличаются
        assert not np.array_equal(arr1, arr2), \
            "Upsampling должен давать другой результат дизеринга"
