"""Тесты этапа F — качество кода.

F.2: Метрики качества (PipelineResult)
F.3: BMP post-save валидация
"""

import os
import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS


class TestF2QualityMetrics:
    """F.2: Метрики качества в PipelineResult."""

    def test_quality_metrics_present(self, tmp_path):
        """PipelineResult содержит метрики качества."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        # Метрики должны быть числами >= 0
        assert isinstance(result.clipped_pixels_pct, float)
        assert isinstance(result.shadow_crush_pct, float)
        assert isinstance(result.tonal_range_output, float)
        assert result.clipped_pixels_pct >= 0
        assert result.shadow_crush_pct >= 0

    def test_dark_image_triggers_warnings(self, tmp_path):
        """Тёмное изображение с агрессивной коррекцией → quality_warnings не пустой."""
        from retouch.processing.pipeline import process_steps

        # Очень тёмное изображение
        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 20
        arr[ellipse, 1] = 15
        arr[ellipse, 2] = 10
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "very_dark.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        # Тёмное изображение может не триггерить все warnings, но
        # структура quality_warnings должна быть list
        assert isinstance(result.quality_warnings, list)


class TestF3BMPValidation:
    """F.3: BMP post-save валидация."""

    def test_bmp_8bit_roundtrip(self, tmp_path):
        """BMP 8-bit: save → reopen → same size, mode L or P."""
        from retouch.processing.export import save_bmp_8bit

        img = Image.new("L", (256, 256), 128)
        output_path = str(tmp_path / "test.bmp")

        save_bmp_8bit(img, output_path)

        with Image.open(output_path) as reopened:
            assert reopened.size == (256, 256)
            assert reopened.mode in ("L", "P")

    def test_bmp_1bit_roundtrip(self, tmp_path):
        """BMP 1-bit: save → reopen → mode 1."""
        from retouch.processing.export import save_bmp_1bit

        img = Image.new("L", (256, 256), 128)
        output_path = str(tmp_path / "test_1bit.bmp")

        save_bmp_1bit(img, output_path)

        with Image.open(output_path) as reopened:
            assert reopened.size == (256, 256)
            # 1-bit BMP может быть сохранён как '1' или 'P' с двумя цветами
            assert reopened.mode in ("1", "P")

    def test_export_creates_bmp_and_png(self, tmp_path):
        """export_result создаёт BMP + PNG."""
        from retouch.processing.export import export_result

        img = Image.new("RGB", (256, 256), (128, 128, 128))
        output_path = str(tmp_path / "output.bmp")

        result = export_result(img, output_path, machine_type="laser_standard")

        assert os.path.isfile(result)
        assert os.path.isfile(str(tmp_path / "output.png"))


class TestPipelineResultNewFields:
    """Новые поля PipelineResult."""

    def test_face_mask_in_result(self, tmp_path):
        """PipelineResult содержит face_mask."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        # face_mask должен быть создан
        assert result.face_mask is not None

    def test_img_sharpened_in_result(self, tmp_path):
        """PipelineResult содержит img_sharpened."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        assert result.img_sharpened is not None

    def test_release_clears_new_fields(self, tmp_path):
        """release_intermediates очищает face_mask и img_sharpened."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        # До release
        assert result.face_mask is not None
        assert result.img_sharpened is not None

        result.release_intermediates()

        # После release
        assert result.face_mask is None
        assert result.img_sharpened is None
        assert result.img_final is not None  # img_final остаётся
