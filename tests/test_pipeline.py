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

        img = Image.fromarray(arr, "RGBA")
        path = str(tmp_path / "input.png")
        img.save(path, "PNG")
        return path

    def test_laser_pipeline_produces_output(self, tmp_path):
        """Laser-пайплайн создаёт TIFF и PNG."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")
        output_png = str(tmp_path / "output.png")

        process(input_path, output_tiff, machine_type="laser", config=DEFAULTS)

        assert os.path.isfile(output_tiff), "TIFF не создан"
        assert os.path.isfile(output_png), "PNG не создан"
        assert os.path.getsize(output_tiff) > 0, "TIFF пустой"
        assert os.path.getsize(output_png) > 0, "PNG пустой"

    def test_impact_pipeline_produces_output(self, tmp_path):
        """Impact-пайплайн создаёт TIFF и PNG."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")

        process(input_path, output_tiff, machine_type="impact", config=DEFAULTS)

        assert os.path.isfile(output_tiff)

    def test_result_not_empty(self, tmp_path):
        """Результат — не пустое изображение (не полностью чёрный)."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")

        process(input_path, output_tiff, machine_type="laser", config=DEFAULTS)

        result = Image.open(output_tiff)
        arr = np.array(result)
        assert arr.mean() > 10, "Результат не должен быть полностью чёрным"

    def test_result_has_black_background(self, tmp_path):
        """Результат содержит >=25% чёрного фона."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")

        process(input_path, output_tiff, machine_type="laser", config=DEFAULTS)

        result = Image.open(output_tiff)
        arr = np.array(result)
        black_mask = (arr[..., 0] < 10) & (arr[..., 1] < 10) & (arr[..., 2] < 10)
        black_ratio = black_mask.sum() / black_mask.size
        assert black_ratio >= 0.25, \
            f"Доля чёрного фона {black_ratio:.1%} ниже минимума 25%"

    def test_no_severe_overexposure(self, tmp_path):
        """Результат не пересвечен (<5% пикселей >250)."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")

        process(input_path, output_tiff, machine_type="laser", config=DEFAULTS)

        result = Image.open(output_tiff)
        arr = np.array(result)
        # Считаем пересвет по всем каналам
        overexposed = (arr.min(axis=-1) > 250)
        overexposed_ratio = overexposed.sum() / overexposed.size
        assert overexposed_ratio < 0.30, \
            f"Слишком много пересвеченных пикселей: {overexposed_ratio:.1%}"

    def test_custom_glow_override(self, tmp_path):
        """Переопределение glow_size и glow_opacity через CLI-аргументы."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")

        process(
            input_path, output_tiff, machine_type="laser",
            glow_size_override=50, glow_opacity_override=35,
            config=DEFAULTS,
        )

        assert os.path.isfile(output_tiff)

    def test_result_is_rgb(self, tmp_path):
        """Результат — RGB-изображение."""
        from retouch.processing.pipeline import process

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")

        process(input_path, output_tiff, machine_type="laser", config=DEFAULTS)

        result = Image.open(output_tiff)
        assert result.mode == "RGB", f"Результат должен быть RGB, а не {result.mode}"

    def test_no_validate_mode(self, tmp_path):
        """Режим --no-validate: обработка без проверки хромакея."""
        from retouch.processing.pipeline import process

        # Создаём изображение БЕЗ хромакея
        arr = np.full((512, 512, 4), [120, 100, 80, 255], dtype=np.uint8)
        img = Image.fromarray(arr, "RGBA")
        input_path = str(tmp_path / "no_chroma.png")
        img.save(input_path, "PNG")

        output_tiff = str(tmp_path / "output.tiff")

        # Конфигурация с выключенной валидацией
        config = {
            "processing": {
                "min_blue_ratio": 0.0,
                "min_resolution": 0,
                "blue_threshold": 30,
                "fringe_radius": 0,
                "result_min_black_ratio": 0.0,
                "laser": DEFAULTS["processing"]["laser"],
            },
            "vignette": DEFAULTS["vignette"],
        }

        # Не должно упасть — валидация отключена
        process(input_path, output_tiff, machine_type="laser", config=config)
        assert os.path.isfile(output_tiff)


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

        img = Image.fromarray(arr, "RGBA")
        path = str(tmp_path / "input.png")
        img.save(path, "PNG")
        return path

    def test_process_steps_returns_pipeline_result(self, tmp_path):
        """process_steps() возвращает PipelineResult без сохранения файлов."""
        from retouch.processing.pipeline import process_steps, PipelineResult

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser", config=DEFAULTS)

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
        result = process_preview(input_path, machine_type="laser",
                                  config=DEFAULTS, max_size=768)

        assert isinstance(result, PipelineResult)
        assert result.width <= 768
        assert result.height <= 768

    def test_process_export_saves_files(self, tmp_path):
        """process_export() сохраняет TIFF + PNG и освобождает промежуточные."""
        from retouch.processing.pipeline import process_export, PipelineResult

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")

        result = process_export(input_path, output_tiff,
                                 machine_type="laser", config=DEFAULTS)

        assert isinstance(result, PipelineResult)
        assert os.path.isfile(output_tiff), "TIFF не создан"
        assert result.img_final is not None
        assert result.img_chromakey is None  # Освобождено

    def test_release_intermediates_keeps_final(self, tmp_path):
        """release_intermediates() освобождает всё кроме img_final."""
        from retouch.processing.pipeline import process_steps, PipelineResult

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser", config=DEFAULTS)

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
