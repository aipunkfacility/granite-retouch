"""T-D1: Расширенные тесты импортов — модули экспортируют ожидаемые имена."""

import pytest


class TestModuleExports:
    """Каждый модуль экспортирует ключевые имена."""

    def test_pipeline_exports_process_steps(self):
        """pipeline.py экспортирует process_steps."""
        from retouch.processing.core.pipeline import process_steps
        assert callable(process_steps)

    def test_pipeline_exports_pipeline_result(self):
        """pipeline.py экспортирует PipelineResult."""
        from retouch.processing.core.pipeline import PipelineResult
        assert PipelineResult is not None

    def test_chromakey_exports_remove_blue(self):
        """chromakey.py экспортирует remove_blue_background."""
        from retouch.processing.detection.chromakey import remove_blue_background
        assert callable(remove_blue_background)

    def test_chromakey_exports_has_scipy(self):
        """chromakey.py экспортирует HAS_SCIPY."""
        from retouch.processing.detection.chromakey import HAS_SCIPY
        assert isinstance(HAS_SCIPY, bool)

    def test_export_exports_export_result(self):
        """export.py экспортирует export_result."""
        from retouch.processing.output.export import export_result
        assert callable(export_result)

    def test_config_exports_defaults(self):
        """config.py экспортирует DEFAULTS."""
        from retouch.config import DEFAULTS
        assert isinstance(DEFAULTS, dict)

    def test_glow_exports_apply_glow(self):
        """glow.py экспортирует apply_glow."""
        from retouch.processing.correction.glow import apply_glow
        assert callable(apply_glow)

    def test_vignette_exports_apply_vignette(self):
        """vignette.py экспортирует apply_vignette."""
        from retouch.processing.output.vignette import apply_vignette
        assert callable(apply_vignette)
