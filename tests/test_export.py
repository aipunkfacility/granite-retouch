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
        from retouch.processing.output.export import stucki_dither
        img = Image.new("L", (100, 100), 128)
        result = stucki_dither(img)
        assert result.mode == "1"

    def test_stucki_preserves_tone(self):
        """Средняя плотность белых точек примерно равна input brightness."""
        from retouch.processing.output.export import stucki_dither
        img = Image.new("L", (200, 200), 128)
        result = stucki_dither(img)
        white_ratio = np.array(result, dtype=np.float32).mean()
        assert 0.40 < white_ratio < 0.60, \
            f"50% серый — примерно 50% белых точек, got {white_ratio:.2%}"

    def test_stucki_output_size_matches_input(self):
        """Размер результата = размер входа."""
        from retouch.processing.output.export import stucki_dither
        img = Image.new("L", (150, 200), 100)
        result = stucki_dither(img)
        assert result.size == (150, 200)


class TestJarvisDithering:
    """Jarvis dithering для laser_80w (SOP 4.1)."""

    def test_jarvis_produces_1bit_output(self):
        """Jarvis даёт 1-bit изображение."""
        from retouch.processing.output.export import jarvis_dither
        img = Image.new("L", (100, 100), 128)
        result = jarvis_dither(img)
        assert result.mode == "1"

    def test_jarvis_preserves_tone(self):
        """Средняя плотность белых точек примерно равна input brightness."""
        from retouch.processing.output.export import jarvis_dither
        img = Image.new("L", (200, 200), 128)
        result = jarvis_dither(img)
        white_ratio = np.array(result, dtype=np.float32).mean()
        assert 0.40 < white_ratio < 0.60, \
            f"50% серый — примерно 50% белых точек, got {white_ratio:.2%}"

    def test_jarvis_output_size_matches_input(self):
        """Размер результата = размер входа."""
        from retouch.processing.output.export import jarvis_dither
        img = Image.new("L", (150, 200), 100)
        result = jarvis_dither(img)
        assert result.size == (150, 200)


class TestDitherMethodConfig:
    """Выбор алгоритма дизеринга и режима экспорта из конфига."""

    def test_impact_export_mode_is_8bit(self):
        """Impact: export_mode=8bit → 8-bit grayscale (256 уровней силы удара).

        Ударные станки требуют BMP 8-bit grayscale. dither_method=stucki
        давал 1-bit файл — все полутона лица терялись при дизеринге.
        """
        config = load_config()
        mode = config["processing"]["impact"].get("export_mode", "")
        assert mode == "8bit", (
            f"impact.export_mode='{mode}', ожидается '8bit' (8-bit grayscale для ударных станков)"
        )

    def test_laser_80w_export_mode_is_8bit(self):
        """Laser 80W: export_mode=8bit (Engrave сам растрирует алгоритмами Р1-Р5)."""
        config = load_config()
        mode = config["processing"]["laser_80w"].get("export_mode", "")
        assert mode == "8bit", f"laser_80w export_mode должен быть 8bit, got {mode}"

    def test_laser_standard_export_mode_is_8bit(self):
        """Laser standard: export_mode=8bit."""
        config = load_config()
        mode = config["processing"]["laser_standard"].get("export_mode", "")
        assert mode == "8bit", f"laser_standard export_mode должен быть 8bit, got {mode}"

    def test_laser_80w_stone_gamma_is_1(self):
        """Laser 80W: stone_gamma=1.0 при 8bit (Engrave сам управляет яркостью)."""
        config = load_config()
        gamma = config["processing"]["laser_80w"].get("stone_gamma", 0)
        assert gamma == 1.0, f"laser_80w stone_gamma должен быть 1.0, got {gamma}"

    def test_laser_80w_step_mm_is_025(self):
        """Laser 80W: step_mm=0.250 (по мануалу САУНО: 0.125-0.250 мм для лазера)."""
        config = load_config()
        step = config["processing"]["laser_80w"].get("step_mm", 0)
        assert step == 0.250, f"laser_80w step_mm должен быть 0.250, got {step}"


class TestExportFormatByMachine:
    """Проверка формата BMP по machine_type — все станки = 8bit по умолчанию (v3)."""

    def test_impact_produces_8bit(self, tmp_path):
        """impact + export_mode=8bit → BMP 8-bit grayscale."""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 180)
        out = str(tmp_path / "impact.bmp")
        export_result(img, out, machine_type="impact", fmt="bmp",
                      export_mode="8bit", step_mm=0.300)
        with Image.open(out) as bmp:
            assert bmp.mode != "1", f"Impact даёт 1-bit! mode={bmp.mode} — нужен 8-bit grayscale"
            assert bmp.mode in ("L", "P"), f"Ожидался L/P, получили {bmp.mode}"

    def test_impact_stucki_produces_1bit(self, tmp_path):
        """impact + fmt='bmp_1bit' → 1-bit (явный запрос дизеринга)."""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 180)
        out = str(tmp_path / "impact_stucki.bmp")
        export_result(img, out, machine_type="impact", fmt="bmp_1bit",
                      dither_method_1bit="stucki")
        with Image.open(out) as bmp:
            assert bmp.mode == "1", f"Stucki должен давать 1-bit, got {bmp.mode}"

    def test_laser_80w_produces_8bit_by_default(self, tmp_path):
        """laser_80w + export_mode=8bit → 8-bit BMP (НЕ 1-bit)."""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 180)
        out = str(tmp_path / "laser80w.bmp")
        export_result(img, out, machine_type="laser_80w", fmt="bmp",
                      export_mode="8bit", step_mm=0.250)
        with Image.open(out) as bmp:
            assert bmp.mode in ("L", "P"), f"8-bit expected, got {bmp.mode}"

    def test_laser_80w_1bit_mode_with_dithering(self, tmp_path):
        """laser_80w + export_mode=1bit → 1-bit BMP с Jarvis."""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 180)
        out = str(tmp_path / "laser80w_1bit.bmp")
        export_result(img, out, machine_type="laser_80w", fmt="bmp",
                      export_mode="1bit", dither_method_1bit="jarvis")
        with Image.open(out) as bmp:
            assert bmp.mode == "1"

    def test_laser_standard_produces_8bit(self, tmp_path):
        """laser_standard + export_mode=8bit → 8-bit BMP."""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 200)
        out = str(tmp_path / "laser_std.bmp")
        export_result(img, out, machine_type="laser_standard", fmt="bmp",
                      export_mode="8bit", step_mm=0.300)
        with Image.open(out) as bmp:
            assert bmp.mode in ("L", "P")


class TestDitherUpsampleRemoved:
    """dither_upsample удалён — NEAREST downsample на 1-bit был no-op."""

    def test_dither_with_upsample_not_in_module(self):
        """Функция dither_with_upsample удалена из модуля export."""
        import retouch.processing.output.export as exp_mod
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
        import retouch.processing.output.export as exp_mod
        from retouch.processing.output.export import jarvis_dither, _error_diffusion_dither

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
        import retouch.processing.output.export as exp_mod
        from retouch.processing.output.export import stucki_dither, _error_diffusion_dither

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
        from retouch.processing.output.export import stucki_dither
        import retouch.processing.output.export as exp_mod

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
        from retouch.processing.output.export import _apply_dither
        img = Image.new("L", (50, 50), 128)
        result = _apply_dither(img)
        assert result.mode == "1"

    def test_apply_dither_floyd_steinberg_redirects_to_jarvis(self):
        """_apply_dither('floyd_steinberg') → jarvis (deprecated, но не падает)."""
        from retouch.processing.output.export import _apply_dither, jarvis_dither
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
        from retouch.processing.output.export import save_bmp_8bit

        img = Image.new("L", (256, 256), 128)
        output_path = str(tmp_path / "test.bmp")

        save_bmp_8bit(img, output_path)

        with Image.open(output_path) as reopened:
            assert reopened.size == (256, 256)
            assert reopened.mode in ("L", "P")

    def test_bmp_8bit_palette_mode_converted(self, tmp_path):
        """BE-L3: save_bmp_8bit конвертирует mode 'P' в 'L' перед сохранением."""
        from retouch.processing.output.export import save_bmp_8bit

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
        from retouch.processing.output.export import _error_diffusion_dither
        import inspect
        sig = inspect.signature(_error_diffusion_dither)
        assert sig.return_annotation is not inspect.Parameter.empty, \
            "_error_diffusion_dither должен иметь return type hint"

    def test_bmp_1bit_roundtrip(self, tmp_path):
        """BMP 1-bit: save -> reopen -> mode 1 or P."""
        from retouch.processing.output.export import save_bmp_1bit

        img = Image.new("L", (256, 256), 128)
        output_path = str(tmp_path / "test_1bit.bmp")

        save_bmp_1bit(img, output_path)

        with Image.open(output_path) as reopened:
            assert reopened.size == (256, 256)
            assert reopened.mode in ("1", "P")

    def test_export_creates_bmp_and_png(self, tmp_path):
        """export_result с save_png_preview=True создаёт BMP + PNG."""
        from retouch.processing.output.export import export_result

        img = Image.new("RGB", (256, 256), (128, 128, 128))
        output_path = str(tmp_path / "output.bmp")

        result = export_result(img, output_path, machine_type="laser_standard",
                               save_png_preview=True)

        assert os.path.isfile(result)
        assert os.path.isfile(str(tmp_path / "output.png"))

    def test_export_bmp_no_png_by_default(self, tmp_path):
        """export_result без save_png_preview создаёт только BMP."""
        from retouch.processing.output.export import export_result

        img = Image.new("RGB", (256, 256), (128, 128, 128))
        output_path = str(tmp_path / "output.bmp")

        result = export_result(img, output_path, machine_type="laser_standard")

        assert os.path.isfile(result)
        assert not os.path.isfile(str(tmp_path / "output.png")), \
            "PNG-дубликат не должен создаваться по умолчанию"

    def test_floyd_steinberg_redirect_produces_valid_output(self):
        """_apply_dither('floyd_steinberg') → jarvis редирект: примерно 50% белого на grayscale=128."""
        from retouch.processing.output.export import _apply_dither

        img = Image.new("L", (200, 200), 128)
        # floyd_steinberg теперь редиректит на jarvis — не падает
        result = _apply_dither(img, method='floyd_steinberg')

        arr = np.array(result.convert("L"))
        white_pct = (arr > 128).sum() / arr.size * 100

        assert 35 < white_pct < 65, \
            f"При grayscale=128 редирект FS→jarvis даёт примерно 50% белого, got {white_pct:.1f}%"


class TestDPIInBMPHeader:
    """DPI в заголовке BMP из step_mm — чтобы Engrave не ругался."""

    def test_save_bmp_8bit_writes_dpi_from_step_mm(self, tmp_path):
        """8-bit BMP содержит DPI из step_mm в заголовке"""
        from retouch.processing.output.export import save_bmp_8bit
        img = Image.new("L", (100, 100), 128)
        out = str(tmp_path / "dpi_test.bmp")
        save_bmp_8bit(img, out, step_mm=0.250)
        with Image.open(out) as saved:
            dpi_x, dpi_y = saved.info.get("dpi", (0, 0))
            assert dpi_x == pytest.approx(101.6, abs=0.5)

    def test_save_bmp_8bit_dpi_step_030(self, tmp_path):
        """step_mm=0.300 → DPI=84.7"""
        from retouch.processing.output.export import save_bmp_8bit
        img = Image.new("L", (100, 100), 128)
        out = str(tmp_path / "dpi_030.bmp")
        save_bmp_8bit(img, out, step_mm=0.300)
        with Image.open(out) as saved:
            dpi_x, _ = saved.info.get("dpi", (0, 0))
            assert dpi_x == pytest.approx(84.7, abs=0.5)

    def test_save_bmp_8bit_without_step_mm(self, tmp_path):
        """8-bit BMP без step_mm — DPI не пишем"""
        from retouch.processing.output.export import save_bmp_8bit
        img = Image.new("L", (100, 100), 128)
        out = str(tmp_path / "no_dpi.bmp")
        save_bmp_8bit(img, out)
        with Image.open(out) as saved:
            assert saved.mode in ("L", "P")

    def test_export_result_8bit_dpi_in_header(self, tmp_path):
        """export_mode=8bit + step_mm → DPI в заголовке BMP"""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 128)
        out = str(tmp_path / "dpi.bmp")
        path = export_result(img, out, export_mode="8bit", step_mm=0.250)
        with Image.open(path) as saved:
            dpi_x, _ = saved.info.get("dpi", (0, 0))
            assert dpi_x == pytest.approx(101.6, abs=0.5)


class TestExportModeRouting:
    """export_mode routing в export_result()."""

    def test_export_mode_8bit(self, tmp_path):
        """export_mode='8bit' → 8-bit BMP, дизеринг не вызывается"""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 128)
        out = str(tmp_path / "mode8bit.bmp")
        path = export_result(img, out, export_mode="8bit", step_mm=0.300)
        with Image.open(path) as saved:
            assert saved.mode in ("L", "P")

    def test_export_mode_1bit(self, tmp_path):
        """export_mode='1bit' → 1-bit BMP с дизерингом"""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 128)
        out = str(tmp_path / "mode1bit.bmp")
        path = export_result(img, out, export_mode="1bit", dither_method_1bit="jarvis")
        with Image.open(path) as saved:
            assert saved.mode == "1"

    def test_explicit_fmt_overrides_export_mode(self, tmp_path):
        """fmt='bmp_8bit' перекрывает export_mode='1bit'"""
        from retouch.processing.output.export import export_result
        img = Image.new("L", (100, 100), 128)
        out = str(tmp_path / "override.bmp")
        path = export_result(img, out, fmt="bmp_8bit",
                              export_mode="1bit", step_mm=0.300)
        with Image.open(path) as saved:
            assert saved.mode in ("L", "P")  # 8-bit выиграл

    def test_dpi_calculation_formula(self):
        """Проверка формулы DPI = 25.4 / step_mm"""
        assert 25.4 / 0.300 == pytest.approx(84.67, abs=0.1)
        assert 25.4 / 0.250 == pytest.approx(101.6, abs=0.1)
        assert 25.4 / 0.200 == pytest.approx(127.0, abs=0.1)


class TestValidateExport:
    """Пост-валидация BMP: RuntimeError вместо молчаливого брака."""

    def test_validate_export_raises_on_missing_file(self):
        """_validate_export выбрасывает RuntimeError для несуществующего файла."""
        from retouch.processing.core.pipeline import _validate_export
        with pytest.raises(RuntimeError, match="Пост-валидация"):
            _validate_export("/nonexistent/path.bmp", "laser_standard", "bmp")

    def test_validate_export_raises_on_corrupt_bmp(self, tmp_path):
        """_validate_export выбрасывает RuntimeError для повреждённого BMP."""
        from retouch.processing.core.pipeline import _validate_export
        corrupt_path = str(tmp_path / "corrupt.bmp")
        with open(corrupt_path, "w") as f:
            f.write("NOT_A_BMP")
        with pytest.raises(RuntimeError, match="Пост-валидация"):
            _validate_export(corrupt_path, "laser_standard", "bmp")

    def test_validate_export_succeeds_on_valid_bmp(self, tmp_path):
        """_validate_export не выбрасывает для валидного BMP."""
        from retouch.processing.core.pipeline import _validate_export
        img = Image.new("L", (100, 100), 128)
        path = str(tmp_path / "valid.bmp")
        img.save(path, format="BMP")
        # Не должно выбрасывать
        _validate_export(path, "laser_standard", "bmp")
