"""Тесты экспорта — дизеринг, BMP."""

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

    def test_impact_dither_method_is_none(self):
        """Impact: dither_method=none → 8-bit grayscale (256 уровней силы удара).

        Ударные станки требуют BMP 8-bit grayscale. dither_method=stucki
        давал 1-bit файл — все полутона лица терялись при дизеринге.
        """
        config = load_config()
        method = config["processing"]["impact"].get("dither_method", "")
        assert method == "none", (
            f"impact.dither_method='{method}', ожидается 'none' (8-bit grayscale для ударных станков)"
        )

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


class TestExportFormatByMachine:
    """Проверка формата BMP по machine_type — impact=8bit, laser_80w=1bit, laser_standard=8bit."""

    def test_impact_produces_8bit_not_1bit(self, tmp_path):
        """impact + dither_method=none → BMP 8-bit grayscale, не 1-bit."""
        from retouch.processing.export import export_result
        img = Image.new("L", (100, 100), 180)
        out = str(tmp_path / "impact.bmp")
        export_result(img, out, machine_type="impact", fmt="bmp", dither_method="none")
        with Image.open(out) as bmp:
            assert bmp.mode != "1", f"Impact даёт 1-bit! mode={bmp.mode} — нужен 8-bit grayscale"
            assert bmp.mode in ("L", "P"), f"Ожидался L/P, получили {bmp.mode}"

    def test_impact_stucki_produces_1bit(self, tmp_path):
        """impact + dither_method=stucki → 1-bit (подтверждение что баг был)."""
        from retouch.processing.export import export_result
        img = Image.new("L", (100, 100), 180)
        out = str(tmp_path / "impact_stucki.bmp")
        export_result(img, out, machine_type="impact", fmt="bmp", dither_method="stucki")
        with Image.open(out) as bmp:
            assert bmp.mode == "1", f"Stucki должен давать 1-bit, got {bmp.mode}"

    def test_laser_80w_produces_1bit(self, tmp_path):
        """laser_80w + dither_method=jarvis → 1-bit BMP."""
        from retouch.processing.export import export_result
        img = Image.new("L", (100, 100), 180)
        out = str(tmp_path / "laser80w.bmp")
        export_result(img, out, machine_type="laser_80w", fmt="bmp",
                      dither_method="jarvis")
        with Image.open(out) as bmp:
            assert bmp.mode == "1"

    def test_laser_standard_produces_8bit(self, tmp_path):
        """laser_standard + dither_method=none → 8-bit BMP."""
        from retouch.processing.export import export_result
        img = Image.new("L", (100, 100), 200)
        out = str(tmp_path / "laser_std.bmp")
        export_result(img, out, machine_type="laser_standard", fmt="bmp", dither_method="none")
        with Image.open(out) as bmp:
            assert bmp.mode in ("L", "P")


class TestDitherUpsampleRemoved:
    """dither_upsample удалён — NEAREST downsample на 1-bit был no-op."""

    def test_dither_with_upsample_not_in_module(self):
        """Функция dither_with_upsample удалена из модуля export."""
        import retouch.processing.export as exp_mod
        assert not hasattr(exp_mod, 'dither_with_upsample'), \
            "dither_with_upsample должна быть удалена из модуля"

    def test_no_dither_upsample_in_defaults(self):
        """DEFAULTS laser_80w не содержит dither_upsample."""
        from retouch.config import DEFAULTS
        assert "dither_upsample" not in DEFAULTS["processing"]["laser_80w"], \
            "dither_upsample должен быть удалён из DEFAULTS"


class TestNumbaDithering:
    """Numba-ускоренный дизеринг."""

    def test_jarvis_same_result_python_vs_numba(self):
        """Jarvis с Numba даёт тот же результат что и чистый Python."""
        import retouch.processing.export as exp_mod
        from retouch.processing.export import jarvis_dither, _error_diffusion_dither

        img = Image.new("L", (50, 50), 128)

        # Python fallback — вызываем _error_diffusion_dither напрямую
        weights = [
            (1, 0, 7/48), (2, 0, 5/48),
            (-2, 1, 3/48), (-1, 1, 5/48), (0, 1, 7/48), (1, 1, 5/48), (2, 1, 3/48),
            (-2, 2, 1/48), (-1, 2, 3/48), (0, 2, 5/48), (1, 2, 3/48), (2, 2, 1/48),
        ]
        was_numba = exp_mod.HAS_NUMBA
        try:
            exp_mod.HAS_NUMBA = False
            result_python = _error_diffusion_dither(img, weights)
        finally:
            exp_mod.HAS_NUMBA = was_numba

        # Через публичный API (может использовать Numba)
        result_api = jarvis_dither(img)

        arr_python = np.array(result_python.convert("L"))
        arr_api = np.array(result_api.convert("L"))
        assert np.array_equal(arr_python, arr_api), \
            "Numba-результат должен совпадать с Python-реализацией"

    def test_stucki_same_result_python_vs_numba(self):
        """Stucki с Numba даёт тот же результат что и чистый Python."""
        import retouch.processing.export as exp_mod
        from retouch.processing.export import stucki_dither, _error_diffusion_dither

        img = Image.new("L", (50, 50), 128)

        weights = [
            (1, 0, 8/42), (2, 0, 4/42),
            (-2, 1, 2/42), (-1, 1, 4/42), (0, 1, 8/42), (1, 1, 4/42), (2, 1, 2/42),
            (-2, 2, 1/42), (-1, 2, 2/42), (0, 2, 4/42), (1, 2, 2/42), (2, 2, 1/42),
        ]
        was_numba = exp_mod.HAS_NUMBA
        try:
            exp_mod.HAS_NUMBA = False
            result_python = _error_diffusion_dither(img, weights)
        finally:
            exp_mod.HAS_NUMBA = was_numba

        result_api = stucki_dither(img)

        arr_python = np.array(result_python.convert("L"))
        arr_api = np.array(result_api.convert("L"))
        assert np.array_equal(arr_python, arr_api), \
            "Stucki Numba-результат должен совпадать с Python-реализацией"

    @pytest.mark.slow
    def test_dither_speed_with_numba(self):
        """Numba-версия значительно быстрее."""
        import time
        from retouch.processing.export import stucki_dither
        import retouch.processing.export as exp_mod

        if os.getenv("CI"):
            pytest.skip("Slow on CI")

        if not exp_mod.HAS_NUMBA:
            pytest.skip("Numba not installed")

        img = Image.new("L", (200, 200), 128)

        # Прогрев JIT
        stucki_dither(img)

        start = time.monotonic()
        stucki_dither(img)
        elapsed = time.monotonic() - start

        # 200×200 Python: ~2-5 сек. Numba: <0.1 сек
        assert elapsed < 2.0, f"Numba-дизеринг слишком медленный: {elapsed:.3f}s"

    def test_apply_dither_default_is_jarvis(self):
        """_apply_dither без метода → jarvis."""
        from retouch.processing.export import _apply_dither
        img = Image.new("L", (50, 50), 128)
        result = _apply_dither(img)
        assert result.mode == "1"

    def test_apply_dither_floyd_steinberg_redirects_to_jarvis(self):
        """_apply_dither('floyd_steinberg') → jarvis (deprecated, но не падает)."""
        from retouch.processing.export import _apply_dither, jarvis_dither
        img = Image.new("L", (50, 50), 128)
        result_fs = _apply_dither(img, method='floyd_steinberg')
        result_jarvis = jarvis_dither(img)
        assert np.array_equal(np.array(result_fs), np.array(result_jarvis)), \
            "floyd_steinberg должен редиректить на jarvis с тем же результатом"

    def test_floyd_steinberg_dither_not_in_public_api(self):
        """floyd_steinberg_dither удалён из __all__."""
        from retouch.processing import __all__
        assert "floyd_steinberg_dither" not in __all__, \
            "floyd_steinberg_dither должен быть удалён из __all__"


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

    def test_bmp_8bit_palette_mode_converted(self, tmp_path):
        """BE-L3: save_bmp_8bit конвертирует mode 'P' в 'L' перед сохранением."""
        from retouch.processing.export import save_bmp_8bit

        # Создаём palette-изображение через конвертацию из RGB
        img_rgb = Image.new("RGB", (100, 100), (128, 128, 128))
        img = img_rgb.convert("P")
        output_path = str(tmp_path / "palette.bmp")

        save_bmp_8bit(img, output_path)

        with Image.open(output_path) as reopened:
            assert reopened.size == (100, 100)
            assert reopened.mode in ("L", "P"), f"Ожидался L/P, получили {reopened.mode}"

    def test_error_diffusion_dither_has_return_type(self):
        """BE-M5: _error_diffusion_dither имеет return type hint."""
        from retouch.processing.export import _error_diffusion_dither
        import inspect
        sig = inspect.signature(_error_diffusion_dither)
        assert sig.return_annotation is not inspect.Parameter.empty, \
            "_error_diffusion_dither должен иметь return type hint"

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
        """export_result с save_png_preview=True создаёт BMP + PNG."""
        from retouch.processing.export import export_result

        img = Image.new("RGB", (256, 256), (128, 128, 128))
        output_path = str(tmp_path / "output.bmp")

        result = export_result(img, output_path, machine_type="laser_standard",
                               save_png_preview=True)

        assert os.path.isfile(result)
        assert os.path.isfile(str(tmp_path / "output.png"))

    def test_export_bmp_no_png_by_default(self, tmp_path):
        """export_result без save_png_preview создаёт только BMP."""
        from retouch.processing.export import export_result

        img = Image.new("RGB", (256, 256), (128, 128, 128))
        output_path = str(tmp_path / "output.bmp")

        result = export_result(img, output_path, machine_type="laser_standard")

        assert os.path.isfile(result)
        assert not os.path.isfile(str(tmp_path / "output.png")), \
            "PNG-дубликат не должен создаваться по умолчанию"

    def test_floyd_steinberg_redirect_produces_valid_output(self):
        """_apply_dither('floyd_steinberg') → jarvis редирект: примерно 50% белого на grayscale=128."""
        from retouch.processing.export import _apply_dither

        img = Image.new("L", (200, 200), 128)
        # floyd_steinberg теперь редиректит на jarvis — не падает
        result = _apply_dither(img, method='floyd_steinberg')

        arr = np.array(result.convert("L"))
        white_pct = (arr > 128).sum() / arr.size * 100

        assert 35 < white_pct < 65, \
            f"При grayscale=128 редирект FS→jarvis даёт примерно 50% белого, got {white_pct:.1f}%"


class TestValidateExport:
    """Пост-валидация BMP: RuntimeError вместо молчаливого брака."""

    def test_validate_export_raises_on_missing_file(self):
        """_validate_export выбрасывает RuntimeError для несуществующего файла."""
        from retouch.processing.pipeline import _validate_export
        with pytest.raises(RuntimeError, match="Пост-валидация"):
            _validate_export("/nonexistent/path.bmp", "laser_standard", "bmp")

    def test_validate_export_raises_on_corrupt_bmp(self, tmp_path):
        """_validate_export выбрасывает RuntimeError для повреждённого BMP."""
        from retouch.processing.pipeline import _validate_export
        corrupt_path = str(tmp_path / "corrupt.bmp")
        with open(corrupt_path, "w") as f:
            f.write("NOT_A_BMP")
        with pytest.raises(RuntimeError, match="Пост-валидация"):
            _validate_export(corrupt_path, "laser_standard", "bmp")

    def test_validate_export_succeeds_on_valid_bmp(self, tmp_path):
        """_validate_export не выбрасывает для валидного BMP."""
        from retouch.processing.pipeline import _validate_export
        img = Image.new("L", (100, 100), 128)
        path = str(tmp_path / "valid.bmp")
        img.save(path, format="BMP")
        # Не должно выбрасывать
        _validate_export(path, "laser_standard", "bmp")
