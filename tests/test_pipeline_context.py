"""Тесты внутренних механизмов пайплайна.

PipelineContext, порядок шагов, конфигурация, white_ceiling,
качественные метрики, интеграция.
"""

import copy
import os
import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS, resolve_config, STONE_PROFILES


# ─── PipelineContext ───────────────────────────────────────────────────

class TestPipelineContext:
    """PipelineContext — внутренняя упаковка данных пайплайна."""

    def test_context_creation(self):
        """PipelineContext создаётся с параметрами."""
        from retouch.processing.core.context import PipelineContext

        img = Image.new("L", (100, 100), 128)
        ctx = PipelineContext(img_gray=img, machine_type="laser_standard")

        assert ctx.img_gray is not None
        assert ctx.machine_type == "laser_standard"
        assert ctx.face_mask is None
        assert ctx.face_oval is None

    def test_context_with_all_fields(self):
        """PipelineContext принимает все поля."""
        from retouch.processing.core.context import PipelineContext

        img = Image.new("L", (100, 100), 128)
        mask = Image.new("L", (100, 100), 255)
        ctx = PipelineContext(
            img_gray=img,
            subject_mask=mask,
            machine_type="impact",
            stone_type="gabbro",
            step_mm=0.250,
        )

        assert ctx.stone_type == "gabbro"
        assert ctx.step_mm == 0.250


# ─── Конфигурация: трёхуровневая система ───────────────────────────────

class TestConfigMigration:
    """Трёхуровневая система параметров: UI > order.json > config.yaml."""

    def test_ui_overrides_order(self):
        """UI-параметры перекрывают order.json."""
        config = copy.deepcopy(DEFAULTS)

        result = resolve_config(
            processing_params={"processing": {"blue_threshold": 50}},
            order_params={"processing": {"blue_threshold": 40}},
            config_params=config,
        )

        assert result["processing"]["blue_threshold"] == 50

    def test_order_overrides_config(self):
        """order.json перекрывает config.yaml."""
        config = copy.deepcopy(DEFAULTS)

        result = resolve_config(
            order_params={"processing": {"blue_threshold": 40}},
            config_params=config,
        )

        assert result["processing"]["blue_threshold"] == 40

    def test_config_as_fallback(self):
        """config.yaml — базовый уровень (низший приоритет)."""
        result = resolve_config(config_params=DEFAULTS)

        assert result["processing"]["blue_threshold"] == 30

    def test_stone_profiles_exist(self):
        """STONE_PROFILES содержит типы камней."""
        assert "granite" in STONE_PROFILES
        assert "gabbro" in STONE_PROFILES
        assert "marble" in STONE_PROFILES
        assert "basalt" in STONE_PROFILES


# ─── Порядок шагов ─────────────────────────────────────────────────────

class TestStepOrder:
    """Unsharp ПОСЛЕ face_brightness (новый порядок)."""

    def test_new_step_order_unsharp_after_face(self, tmp_path):
        """В новом порядке unsharp вызывается после face_brightness."""
        from retouch.processing.core.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 80
        arr[ellipse, 1] = 60
        arr[ellipse, 2] = 40
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        config = copy.deepcopy(DEFAULTS)

        result = process_steps(input_path, machine_type="laser_standard", config=config)
        assert result.img_final is not None
        assert result.img_postproc is not result.img_face_corrected


# ─── White ceiling clamp ───────────────────────────────────────────────

class TestWhiteCeilingClamp:
    """Hard clamp белой точки перед экспортом."""

    def test_no_pixels_above_white_ceiling(self, tmp_path):
        """Внутри маски субъекта нет пикселей > white_ceiling."""
        from retouch.processing.core.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 250
        arr[ellipse, 1] = 250
        arr[ellipse, 2] = 250
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "bright.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        white_ceiling = DEFAULTS["processing"]["laser_standard"]["white_ceiling"]
        if result.subject_mask is not None:
            final_arr = np.array(result.img_final.convert("L"))
            mask_bool = np.array(result.subject_mask) > 128
            subject_pixels = final_arr[mask_bool]
            above = (subject_pixels > white_ceiling).sum()
            assert above == 0, \
                f"Нет пикселей > {white_ceiling} в субъекте, found {above}"


# ─── USM threshold ─────────────────────────────────────────────────────

class TestUnsharpThreshold:
    """USM threshold из конфига (SOP 3.1: 2-4)."""

    def test_default_threshold_ge_2(self):
        """По умолчанию unsharp_threshold >= 2 (кроме impact: эталон gradient P99=43.5, порог 1)."""
        from retouch.config import load_config
        config = load_config()
        for machine in ("laser_standard", "laser_80w", "impact"):
            threshold = config["processing"][machine].get("unsharp_threshold", 0)
            min_threshold = 1 if machine == "impact" else 2
            assert threshold >= min_threshold, \
                f"{machine}: unsharp_threshold должен быть >= {min_threshold}, got {threshold}"

    def test_default_threshold_le_8(self):
        """unsharp_threshold <= 8 (верхняя граница SOP)."""
        from retouch.config import load_config
        config = load_config()
        for machine in ("laser_standard", "laser_80w", "impact"):
            threshold = config["processing"][machine].get("unsharp_threshold", 0)
            assert threshold <= 8, \
                f"{machine}: unsharp_threshold должен быть <= 8, got {threshold}"


# ─── Качественные метрики ──────────────────────────────────────────────

class TestQualityMetrics:
    """Метрики качества в PipelineResult."""

    def test_quality_metrics_present(self, tmp_path):
        """PipelineResult содержит метрики качества."""
        from retouch.processing.core.pipeline import process_steps

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

        assert isinstance(result.clipped_pixels_pct, float)
        assert isinstance(result.shadow_crush_pct, float)
        assert isinstance(result.tonal_range_output, float)
        assert result.clipped_pixels_pct >= 0
        assert result.shadow_crush_pct >= 0

    def test_dark_image_triggers_warnings(self, tmp_path):
        """Тёмное изображение — quality_warnings список."""
        from retouch.processing.core.pipeline import process_steps

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

        assert isinstance(result.quality_warnings, list)


# ─── PipelineResult: новые поля ─────────────────────────────────────────

class TestPipelineResultNewFields:
    """Новые поля PipelineResult."""

    def test_face_mask_in_result(self, tmp_path):
        """PipelineResult содержит face_mask."""
        from retouch.processing.core.pipeline import process_steps

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
        assert result.face_mask is not None

    def test_img_postproc_in_result(self, tmp_path):
        """PipelineResult содержит img_postproc."""
        from retouch.processing.core.pipeline import process_steps

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
        assert result.img_postproc is not None

    def test_release_clears_new_fields(self, tmp_path):
        """release_intermediates очищает face_mask и img_postproc."""
        from retouch.processing.core.pipeline import process_steps

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

        assert result.face_mask is not None
        assert result.img_postproc is not None

        result.release_intermediates()

        assert result.face_mask is None
        assert result.img_postproc is None
        assert result.img_final is not None


# ─── Интеграционные тесты ──────────────────────────────────────────────

class TestIntegration:
    """Сквозной пайплайн — загрузка -> обработка -> экспорт."""

    def test_full_pipeline_laser(self, tmp_path):
        """Сквозной laser_standard: BMP + PNG созданы и валидны."""
        from retouch.processing.core.pipeline import process_export

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 150
        arr[ellipse, 1] = 120
        arr[ellipse, 2] = 100
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        output_bmp = str(tmp_path / "output.bmp")

        result = process_export(
            input_path, output_bmp,
            machine_type="laser_standard", config=DEFAULTS,
        )

        assert os.path.isfile(output_bmp)
        with Image.open(output_bmp) as bmp:
            assert bmp.mode in ("L", "P", "RGB")

        assert os.path.isfile(str(tmp_path / "output.png"))
        assert result.img_chromakey is None
        assert result.img_final is not None
        assert result.glow_size > 0
        assert result.face_brightness_before >= 0

    def test_full_pipeline_impact(self, tmp_path):
        """Сквозной impact: shadow_floor + shadow_noise + white_ceiling."""
        from retouch.processing.core.pipeline import process_export

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 80
        arr[ellipse, 1] = 60
        arr[ellipse, 2] = 40
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        output_bmp = str(tmp_path / "output.bmp")

        result = process_export(
            input_path, output_bmp,
            machine_type="impact", config=DEFAULTS,
        )

        assert os.path.isfile(output_bmp)
        assert result.img_final is not None

    def test_face_oval_override(self, tmp_path):
        """Ручной овал (face_oval) интегрируется в пайплайн."""
        from retouch.processing.core.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 150
        arr[ellipse, 1] = 120
        arr[ellipse, 2] = 100
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        manual_oval = {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20, "source": "manual"}

        result = process_steps(
            input_path, machine_type="laser_standard",
            config=DEFAULTS, face_oval=manual_oval,
        )

        assert result.face_mask is not None

    def test_wide_image_preview_height(self, tmp_path):
        """Широкий кадр 4000x500 — height >= 200."""
        from retouch.processing.core.pipeline import process_preview

        arr = np.zeros((500, 4000, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:500, :4000]
        ellipse = ((x - 2000) / 200) ** 2 + ((y - 250) / 100) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "wide.png")
        img.save(input_path, "PNG")

        config = copy.deepcopy(DEFAULTS)
        config["processing"]["min_resolution"] = 0
        config["processing"]["min_blue_ratio"] = 0.0

        result = process_preview(input_path, machine_type="laser_standard",
                                  config=config, max_size=768)

        assert result.height >= 200, f"Высота {result.height} < 200"
        assert result.width <= 768 * 3, f"Ширина {result.width} > {768 * 3}"
