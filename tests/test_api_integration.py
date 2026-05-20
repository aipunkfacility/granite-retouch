"""Integration tests — profile parameter flows through the full pipeline."""

import pytest
from retouch.processing.core.plan import PROFILE_PRESERVE, PROFILE_STANDARD


class TestProfilePreviewIntegration:
    """Profile parameter is respected by the preview pipeline."""

    @pytest.fixture
    def chromakey_png(self, tmp_path):
        """Create a synthetic chromakey PNG."""
        import numpy as np
        from PIL import Image

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255  # Blue background
        arr[..., 3] = 255
        # Subject ellipse
        cx, cy = 256, 256
        rx, ry = 128, 150
        y_c, x_c = np.ogrid[:512, :512]
        ellipse = ((x_c - cx) / rx) ** 2 + ((y_c - cy) / ry) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        path = str(tmp_path / "input.png")
        img.save(path, "PNG")
        return path

    def test_preserve_profile_skips_levels_in_preview(self, chromakey_png):
        """Preserve profile: step_metrics should NOT contain 'levels'."""
        from retouch.processing.core.pipeline import process_preview

        result = process_preview(
            chromakey_png,
            machine_type="laser_standard",
            profile="preserve",
        )

        step_names = [r.step_name for r in result.step_metrics]
        assert "levels" not in step_names, "preserve should skip levels"
        assert "face_correction" not in step_names, "preserve should skip face_correction"
        assert "unsharp" not in step_names, "preserve should skip unsharp"
        assert "glow" in step_names, "preserve should include glow"

    def test_standard_profile_runs_all_steps_in_preview(self, chromakey_png):
        """Standard profile: step_metrics should contain all steps."""
        from retouch.processing.core.pipeline import process_preview

        result = process_preview(
            chromakey_png,
            machine_type="laser_standard",
            profile="standard",
        )

        step_names = [r.step_name for r in result.step_metrics]
        assert "levels" in step_names
        assert "face_correction" in step_names
        assert "unsharp" in step_names
        assert "glow" in step_names
        assert "postproc" in step_names

    def test_preserve_and_standard_produce_different_results(self, chromakey_png):
        """Preserve and standard produce different output images."""
        import numpy as np
        from retouch.processing.core.pipeline import process_preview

        result_preserve = process_preview(
            chromakey_png,
            machine_type="laser_standard",
            profile="preserve",
        )
        result_standard = process_preview(
            chromakey_png,
            machine_type="laser_standard",
            profile="standard",
        )

        arr_p = np.array(result_preserve.img_final, dtype=np.float32)
        arr_s = np.array(result_standard.img_final, dtype=np.float32)

        assert not np.allclose(arr_p, arr_s), (
            "preserve and standard should produce different results"
        )
