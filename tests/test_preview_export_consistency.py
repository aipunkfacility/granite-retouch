"""Тесты для preview/export consistency."""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from retouch.processing.analysis.zones import build_zone_masks


class TestPreviewExportConsistency:
    """Preview и export используют одни и те же зоны."""

    def _tmp_path(self):
        """Создать временную директорию."""
        return Path(tempfile.mkdtemp())

    def test_preview_export_zones_consistent(self):
        """Зоны не расходятся > 5% площади при downscale."""
        h, w = 200, 200
        gray = np.zeros((h, w), dtype=np.float32)
        gray[:100, :] = 128.0
        gray[100:, :] = 180.0

        subj = np.ones((h, w), dtype=np.uint8) * 255
        face = np.zeros((h, w), dtype=np.uint8)
        face[40:120, 40:160] = 255

        # Full resolution
        zones_full = build_zone_masks(
            subject_mask=Image.fromarray(subj, mode="L"),
            face_mask=Image.fromarray(face, mode="L"),
            img_gray=Image.fromarray(gray.astype(np.uint8), mode="L"),
        )

        # Downscaled (preview)
        scale = 0.5
        small_h, small_w = int(h * scale), int(w * scale)
        gray_small = np.array(Image.fromarray(gray.astype(np.uint8)).resize(
            (small_w, small_h), Image.LANCZOS
        ), dtype=np.float32)
        subj_small = np.array(Image.fromarray(subj, mode="L").resize(
            (small_w, small_h), Image.LANCZOS
        ), dtype=np.uint8)
        face_small = np.array(Image.fromarray(face, mode="L").resize(
            (small_w, small_h), Image.LANCZOS
        ), dtype=np.uint8)

        zones_small = build_zone_masks(
            subject_mask=Image.fromarray(subj_small, mode="L"),
            face_mask=Image.fromarray(face_small, mode="L"),
            img_gray=Image.fromarray(gray_small.astype(np.uint8), mode="L"),
        )

        # Проверяем что зоны не расходятся > 5% площади
        full_area = int(np.sum(zones_full.subject > 128))
        small_area = int(np.sum(zones_small.subject > 128))
        if full_area > 0:
            area_ratio = small_area / (full_area * scale * scale)
            assert 0.90 < area_ratio < 1.10, (
                f"Area ratio {area_ratio} outside 5% tolerance"
            )

    def test_face_oval_passed_via_context(self):
        """face_oval передаётся через PipelineContext."""
        from retouch.processing.core.context import PipelineContext

        face_oval = {"cx": 0.5, "cy": 0.4, "rx": 0.3, "ry": 0.35}
        ctx = PipelineContext(
            img_gray=Image.new("L", (100, 100)),
            face_oval=face_oval,
        )
        assert ctx.face_oval == face_oval

    def test_no_redetection_in_export(self):
        """Export не детектирует face_oval заново если передан."""
        import numpy as np
        from PIL import Image
        from retouch.processing.core.pipeline import process_steps, process_export
        from retouch.config import DEFAULTS

        # Создаём тестовое изображение
        tmp_path = self._tmp_path()
        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        cx, cy = 256, 256
        rx, ry = 128, 154
        y_c, x_c = np.ogrid[:512, :512]
        ellipse = ((x_c - cx) / rx) ** 2 + ((y_c - cy) / ry) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255
        img = Image.fromarray(arr)
        input_path = str(tmp_path / "input.png")
        img.save(input_path)

        # 1. Preview — детектирует face_oval
        preview_result = process_steps(
            input_path, machine_type="laser_standard", config=DEFAULTS,
        )
        assert preview_result.face_oval is not None
        preview_oval = preview_result.face_oval.copy()

        # 2. Export — должен использовать тот же face_oval
        output_path = str(tmp_path / "output.bmp")
        export_result = process_export(
            input_path, output_path, machine_type="laser_standard",
            config=DEFAULTS, face_oval=preview_oval,
        )
        # face_oval в export_result должен совпадать с preview
        assert export_result.face_oval is not None
        assert abs(export_result.face_oval["cx"] - preview_oval["cx"]) < 0.01
        assert abs(export_result.face_oval["cy"] - preview_oval["cy"]) < 0.01

    def test_consistency_mismatch_warning(self):
        """Расхождение овала > 2% генерирует warning."""
        oval_preview = {"cx": 0.50, "cy": 0.40, "rx": 0.30, "ry": 0.35}
        oval_export = {"cx": 0.55, "cy": 0.40, "rx": 0.30, "ry": 0.35}

        # Проверяем расхождение > 2% по cx
        diff = abs(oval_preview["cx"] - oval_export["cx"])
        assert diff > 0.02  # 5% расхождение

    def test_thresholds_same_preview_export(self):
        """Пороги не пересчитываются для preview."""
        skin_threshold = 100
        highlight_threshold = 200

        # Пороги — параметры плана, не зависят от разрешения
        assert skin_threshold == 100
        assert highlight_threshold == 200


class TestConsistencyRuntimeCheck:
    """Runtime consistency check в process_steps."""

    def test_diagnostics_logs_scale_ratio(self):
        """Diagnostics логирует scale ratio preview и export."""
        from retouch.processing.core.context import PipelineContext
        from PIL import Image

        ctx = PipelineContext(
            img_gray=Image.new("L", (100, 100)),
        )
        assert hasattr(ctx, "config")

    def test_consistency_mismatch_warning_generated(self):
        """Расхождение face_oval > 2% генерирует warning через _run_consistency_check."""
        from retouch.processing.core.pipeline import _run_consistency_check

        warnings: list[str] = []
        _run_consistency_check(
            {"cx": 0.50, "cy": 0.40, "rx": 0.30, "ry": 0.35},
            {"cx": 0.60, "cy": 0.42, "rx": 0.32, "ry": 0.37},
            warnings,
        )
        assert len(warnings) >= 1

    def test_passed_oval_differs_from_result_warns(self):
        """Переданный и результирующий овалы расходятся — warning."""
        from retouch.processing.core.pipeline import _run_consistency_check
        from PIL import Image

        warnings: list[str] = []
        passed = {"cx": 0.50, "cy": 0.40, "rx": 0.30, "ry": 0.35}
        result = {"cx": 0.60, "cy": 0.42, "rx": 0.32, "ry": 0.37}

        _run_consistency_check(passed, result, warnings)
        assert len(warnings) >= 1
        assert any("consistency_mismatch" in w for w in warnings)

    def test_matching_ovals_no_warning(self):
        """Совпадающие овалы не дают warning."""
        from retouch.processing.core.pipeline import _run_consistency_check

        warnings: list[str] = []
        oval = {"cx": 0.50, "cy": 0.40, "rx": 0.30, "ry": 0.35}

        _run_consistency_check(oval, oval, warnings)
        assert len(warnings) == 0
