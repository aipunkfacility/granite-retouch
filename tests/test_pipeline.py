"""Интеграционные тесты — полный пайплайн process()."""

import os

import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS


class TestPipelineIntegration:
    """Интеграционные тесты полного пайплайна обработки."""

    def _save_chromakey_png(self, tmp_path, width=512, height=512):
        """Создать и сохранить синтетический PNG с хромакеем."""
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        # Синий фон
        arr[..., 2] = 255
        arr[..., 3] = 255
        # Субъект — центральный эллипс
        cx, cy = width // 2, height // 2
        rx, ry = int(width * 0.25), int(height * 0.30)
        y_c, x_c = np.ogrid[:height, :width]
        ellipse = ((x_c - cx) / rx) ** 2 + ((y_c - cy) / ry) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        path = str(tmp_path / "input.png")
        img.save(path, "PNG")
        return path

    def test_laser_pipeline_produces_output(self, tmp_path):
        """Laser-пайплайн создаёт BMP и PNG."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")
        output_png = str(tmp_path / "output.png")

        process(input_path, output_bmp, machine_type="laser_standard", config=DEFAULTS)

        assert os.path.isfile(output_bmp), "BMP не создан"
        assert os.path.isfile(output_png), "PNG не создан"
        assert os.path.getsize(output_bmp) > 0, "BMP пустой"
        assert os.path.getsize(output_png) > 0, "PNG пустой"

    def test_impact_pipeline_produces_output(self, tmp_path):
        """Impact-пайплайн создаёт BMP и PNG."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")

        process(input_path, output_bmp, machine_type="impact", config=DEFAULTS)

        assert os.path.isfile(output_bmp)

    def test_result_not_empty(self, tmp_path):
        """Результат — не пустое изображение (не полностью чёрный)."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")

        process(input_path, output_bmp, machine_type="laser_standard", config=DEFAULTS)

        result = Image.open(output_bmp)
        arr = np.array(result)
        assert arr.mean() > 10, "Результат не должен быть полностью чёрным"

    def test_result_has_black_background(self, tmp_path):
        """Результат содержит >=25% чёрного фона."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")

        process(input_path, output_bmp, machine_type="laser_standard", config=DEFAULTS)

        result = Image.open(output_bmp)
        arr = np.array(result)
        # BMP может быть L или RGB, обрабатываем оба случая
        if arr.ndim == 2:
            black_mask = arr < 10
        else:
            black_mask = (arr[..., 0] < 10) & (arr[..., 1] < 10) & (arr[..., 2] < 10)
        black_ratio = black_mask.sum() / black_mask.size
        assert black_ratio >= 0.25, \
            f"Доля чёрного фона {black_ratio:.1%} ниже минимума 25%"

    def test_no_severe_overexposure(self, tmp_path):
        """Результат не пересвечен (<5% пикселей >250)."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")

        process(input_path, output_bmp, machine_type="laser_standard", config=DEFAULTS)

        result = Image.open(output_bmp)
        arr = np.array(result)
        # BMP может быть L или RGB
        if arr.ndim == 2:
            overexposed = arr > 250
        else:
            overexposed = (arr.min(axis=-1) > 250)
        overexposed_ratio = overexposed.sum() / overexposed.size
        assert overexposed_ratio < 0.30, \
            f"Слишком много пересвеченных пикселей: {overexposed_ratio:.1%}"

    def test_custom_glow_override(self, tmp_path):
        """Переопределение glow_size и glow_opacity через CLI-аргументы."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")

        process(
            input_path, output_bmp, machine_type="laser_standard",
            glow_size_override=50, glow_opacity_override=35,
            config=DEFAULTS,
        )

        assert os.path.isfile(output_bmp)

    def test_result_is_correct_mode(self, tmp_path):
        """Результат — BMP grayscale (8-bit) или RGB."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")

        process(input_path, output_bmp, machine_type="laser_standard", config=DEFAULTS)

        result = Image.open(output_bmp)
        assert result.mode in ("L", "RGB", "P"), f"Unexpected BMP mode: {result.mode}"

    def test_no_validate_mode(self, tmp_path):
        """Режим --no-validate: обработка без проверки хромакея."""
        from retouch.processing.pipeline import process

        # Создаём изображение БЕЗ хромакея
        arr = np.full((512, 512, 4), [120, 100, 80, 255], dtype=np.uint8)
        img = Image.fromarray(arr)
        input_path = str(tmp_path / "no_chroma.png")
        img.save(input_path, "PNG")

        output_bmp = str(tmp_path / "output.bmp")

        # Конфигурация с выключенной валидацией
        config = {
            "processing": {
                "min_blue_ratio": 0.0,
                "min_resolution": 0,
                "blue_threshold": 30,
                "fringe_radius": 0,
                "result_min_black_ratio": 0.0,
                "laser_standard": DEFAULTS["processing"]["laser_standard"],
            },
            "vignette": DEFAULTS["vignette"],
        }

        # Не должно упасть — валидация отключена
        process(input_path, output_bmp, machine_type="laser_standard", config=config)
        assert os.path.isfile(output_bmp)


class TestPipelineStepsAPI:
    """Тесты нового API: process_steps, process_preview, process_export."""

    def _save_chromakey_png(self, tmp_path, width=512, height=512):
        """Создать и сохранить синтетический PNG с хромакеем."""
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        # Синий фон
        arr[..., 2] = 255
        arr[..., 3] = 255
        # Субъект — центральный эллипс
        cx, cy = width // 2, height // 2
        rx, ry = int(width * 0.25), int(height * 0.30)
        y_c, x_c = np.ogrid[:height, :width]
        ellipse = ((x_c - cx) / rx) ** 2 + ((y_c - cy) / ry) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        path = str(tmp_path / "input.png")
        img.save(path, "PNG")
        return path

    def test_process_steps_returns_pipeline_result(self, tmp_path):
        """process_steps() возвращает PipelineResult без сохранения файлов."""
        from retouch.processing.pipeline import process_steps, PipelineResult

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        assert isinstance(result, PipelineResult)
        assert result.img_final is not None
        assert result.img_chromakey is not None
        assert result.width == 512
        assert result.height == 512
        assert result.glow_size > 0
        assert 0.0 <= result.face_brightness_before <= 255.0

    def test_process_preview_returns_small_result(self, tmp_path):
        """process_preview() уменьшает изображение до max_size."""
        from retouch.processing.pipeline import process_preview, PipelineResult

        input_path = self._save_chromakey_png(tmp_path, width=2048, height=2048)
        result = process_preview(input_path, machine_type="laser_standard",
                                  config=DEFAULTS, max_size=768)

        assert isinstance(result, PipelineResult)
        assert result.width <= 768
        assert result.height <= 768

    def test_process_export_saves_files(self, tmp_path):
        """process_export() сохраняет BMP + PNG и освобождает промежуточные."""
        from retouch.processing.pipeline import process_export, PipelineResult

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")

        result = process_export(input_path, output_bmp,
                                 machine_type="laser_standard", config=DEFAULTS)

        assert isinstance(result, PipelineResult)
        assert os.path.isfile(output_bmp), "BMP не создан"
        assert result.img_final is not None
        assert result.img_chromakey is None  # Освобождено

    def test_release_intermediates_keeps_final(self, tmp_path):
        """release_intermediates() освобождает всё кроме img_final."""
        from retouch.processing.pipeline import process_steps, PipelineResult

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        # До release — все промежуточные доступны
        assert result.img_chromakey is not None
        assert result.img_final is not None

        result.release_intermediates()

        # После release — промежуточные None, img_final доступен
        assert result.img_chromakey is None
        assert result.img_gray is None
        assert result.img_glow is None
        assert result.img_leveled is None
        assert result.img_face_corrected is None
        assert result.img_final is not None  # Важно!
        assert result.arch_mask is None
        assert result.subject_mask is None

    def test_process_preview_fixed_glow(self, tmp_path):
        """process_preview() fixes glow at midpoint of range."""
        from retouch.processing.pipeline import process_preview, PipelineResult

        input_path = self._save_chromakey_png(tmp_path)
        result = process_preview(input_path, machine_type="laser_standard", config=DEFAULTS)

        # Glow at midpoint: (40 + 80) // 2 = 60
        assert result.glow_size == 60

    def test_process_export_creates_bmp_and_png(self, tmp_path):
        """process_export() creates both BMP and PNG files."""
        from retouch.processing.pipeline import process_export

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")
        output_png = str(tmp_path / "output.png")

        result = process_export(input_path, output_bmp,
                                 machine_type="laser_standard", config=DEFAULTS)

        assert os.path.isfile(output_bmp), "BMP not created"
        assert os.path.isfile(output_png), "PNG not created"
        assert os.path.getsize(output_bmp) > 0
        assert os.path.getsize(output_png) > 0
        # Intermediates released
        assert result.img_chromakey is None
        assert result.img_final is not None

    def test_process_backward_compatible(self, tmp_path):
        """process() is the backward-compatible CLI wrapper."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_bmp = str(tmp_path / "output.bmp")

        result = process(input_path, output_bmp, machine_type="laser_standard", config=DEFAULTS)
        assert os.path.isfile(output_bmp)
        assert result.img_final is not None

    def test_process_steps_result_has_diagnostics(self, tmp_path):
        """process_steps() result includes all diagnostic fields."""
        from retouch.processing.pipeline import process_steps

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        assert result.glow_size > 0
        assert 0.0 <= result.glow_opacity <= 1.0
        assert result.face_brightness_before >= 0
        assert result.face_brightness_after >= 0
        assert result.black_ratio >= 0
        assert result.blue_ratio >= 0
        assert result.width == 512
        assert result.height == 512

    def test_process_steps_img_final_is_rgb(self, tmp_path):
        """process_steps() img_final is always RGB mode."""
        from retouch.processing.pipeline import process_steps

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        assert result.img_final is not None
        assert result.img_final.mode == "L"

    def test_process_preview_impact_machine(self, tmp_path):
        """process_preview() works with impact machine type."""
        from retouch.processing.pipeline import process_preview, PipelineResult

        input_path = self._save_chromakey_png(tmp_path)
        result = process_preview(input_path, machine_type="impact", config=DEFAULTS)

        assert isinstance(result, PipelineResult)
        assert result.img_final is not None
        # Impact glow midpoint: (10 + 25) // 2 = 17
        assert result.glow_size == 17

    def test_process_steps_keep_intermediates_false(self, tmp_path):
        """process_steps(keep_intermediates=False) освобождает промежуточные."""
        from retouch.processing.pipeline import process_steps

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser_standard",
                               config=DEFAULTS, keep_intermediates=False)

        assert result.img_final is not None
        assert result.img_chromakey is None
        assert result.img_gray is None
        assert result.img_glow is None

    def test_process_steps_keep_intermediates_true(self, tmp_path):
        """process_steps(keep_intermediates=True) сохраняет промежуточные."""
        from retouch.processing.pipeline import process_steps

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser_standard",
                               config=DEFAULTS, keep_intermediates=True)

        assert result.img_final is not None
        assert result.img_chromakey is not None
        assert result.img_gray is not None

    def test_release_intermediates_idempotent(self, tmp_path):
        """Повторный вызов release_intermediates() не падает."""
        from retouch.processing.pipeline import process_steps

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        result.release_intermediates()
        result.release_intermediates()  # Не должно быть AttributeError

        assert result.img_final is not None

    def test_pipeline_result_context_manager(self, tmp_path):
        """with PipelineResult: автоматически освобождает промежуточные."""
        from retouch.processing.pipeline import process_steps
        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        # Используем как context manager
        with result:
            assert result.img_final is not None
            assert result.img_chromakey is not None

        # После выхода из with — промежуточные освобождены
        assert result.img_chromakey is None
        assert result.img_final is not None

    def test_process_steps_with_input_image(self, tmp_path):
        """process_steps(input_image=img) работает без файла на диске."""
        from retouch.processing.pipeline import process_steps

        # Создаём изображение с хромакеем В ПАМЯТИ
        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255; arr[..., 3] = 255  # синий фон
        cx, cy = 256, 256
        rx, ry = 128, 154
        y_c, x_c = np.ogrid[:512, :512]
        ellipse = ((x_c - cx) / rx) ** 2 + ((y_c - cy) / ry) ** 2 <= 1.0
        arr[ellipse, 0] = 180; arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120; arr[ellipse, 3] = 255
        img = Image.fromarray(arr)

        result = process_steps(input_image=img, machine_type="laser_standard",
                               config=DEFAULTS, no_validate=True)
        assert result.img_final is not None
        assert result.width == 512
        assert result.height == 512

    def test_input_image_no_temp_files(self, tmp_path):
        """При input_image не создаётся временных файлов."""
        import tempfile
        import unittest.mock
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255; arr[..., 3] = 255
        arr[200:400, 150:350] = [180, 140, 120, 255]
        img = Image.fromarray(arr)

        with unittest.mock.patch.object(tempfile, 'NamedTemporaryFile',
                                        wraps=tempfile.NamedTemporaryFile) as mock_tmp:
            process_steps(input_image=img, machine_type="laser_standard",
                          config=DEFAULTS, no_validate=True)
            mock_tmp.assert_not_called()

    def test_preview_no_disk_write(self, tmp_path):
        """process_preview не пишет на диск при ресайзе (input_image path)."""
        from retouch.processing.pipeline import process_preview

        # Создаём большой файл для триггера thumbnail
        arr = np.zeros((2048, 2048, 4), dtype=np.uint8)
        arr[..., 2] = 255; arr[..., 3] = 255
        arr[500:1500, 500:1500] = [180, 140, 120, 255]
        img = Image.fromarray(arr)
        input_path = str(tmp_path / "big.png")
        img.save(input_path)

        import tempfile
        import unittest.mock
        with unittest.mock.patch.object(tempfile, 'NamedTemporaryFile',
                                        wraps=tempfile.NamedTemporaryFile) as mock_tmp:
            process_preview(input_path, machine_type="laser_standard",
                            config=DEFAULTS, max_size=768)
            mock_tmp.assert_not_called()

    def test_preview_wide_frame_min_height_200(self, tmp_path):
        """FIX-4: Широкий кадр (panorama) — высота >= 200 после thumbnail.

        Было: thumbnail → height<200 → повторный Image.open().
        Стало: рассчитываем финальный размер заранее — один Image.open().
        """
        from retouch.processing.pipeline import process_preview

        # Панорамное изображение 4000x500 (широкое)
        # При max_size=768: thumbnail → 768x96 (height<200) → пересчёт
        arr = np.zeros((500, 4000, 4), dtype=np.uint8)
        arr[..., 2] = 255; arr[..., 3] = 255  # синий фон
        # Субъект в центре
        arr[100:400, 1500:2500] = [180, 140, 120, 255]
        img = Image.fromarray(arr)
        input_path = str(tmp_path / "panorama.png")
        img.save(input_path)

        result = process_preview(input_path, machine_type="laser_standard",
                                  config=DEFAULTS, max_size=768)

        # D.2: высота должна быть >= 200
        assert result.height >= 200, f"Height {result.height} < 200 (D.2 violation)"
        assert result.img_final is not None

    def test_preview_single_file_open(self, tmp_path):
        """FIX-4: process_preview открывает файл ровно ОДИН раз."""
        from retouch.processing.pipeline import process_preview
        import unittest.mock

        # Панорамное изображение — триггерит D.2 ветку
        arr = np.zeros((500, 4000, 4), dtype=np.uint8)
        arr[..., 2] = 255; arr[..., 3] = 255
        arr[100:400, 1500:2500] = [180, 140, 120, 255]
        img = Image.fromarray(arr)
        input_path = str(tmp_path / "panorama.png")
        img.save(input_path)

        with unittest.mock.patch("retouch.processing.pipeline.Image.open",
                                  wraps=Image.open) as mock_open:
            process_preview(input_path, machine_type="laser_standard",
                            config=DEFAULTS, max_size=768)
            # Ровно один вызов Image.open — не два
            assert mock_open.call_count == 1, (
                f"Image.open вызван {mock_open.call_count} раз, ожидается 1"
            )
