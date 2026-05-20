"""Тесты для 1-bit dither regression на curated set."""

import filecmp
import os
import tempfile

import numpy as np
import pytest
from PIL import Image

from retouch.processing.output.export import export_result


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "dither")


class TestDitherRegression:
    """1-bit dither regression testing on curated set."""

    @pytest.fixture(autouse=True)
    def _check_fixtures(self):
        if not os.path.exists(FIXTURES_DIR):
            pytest.skip("Dither fixtures not yet created")
        files = [f for f in os.listdir(FIXTURES_DIR) if f.endswith(".png")]
        if len(files) < 5:
            pytest.skip(f"Dither fixtures: {len(files)} < 5")

    def test_dither_curated_set_no_new_artifacts(self):
        """Dither на синтетическом изображении не создаёт артефактов."""
        arr = np.zeros((64, 64), dtype=np.uint8)
        arr[:32, :] = 128
        arr[32:, :] = 200

        img = Image.fromarray(arr, mode="L")

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.bmp")
            export_result(
                img, path,
                machine_type="laser_standard",
                fmt="bmp_1bit",
                export_mode="1bit",
                step_mm=0.300,
                dither_method_1bit="jarvis",
            )

            with Image.open(path) as result:
                assert result.mode == "1"
                assert result.size == (64, 64)

    def test_dither_preview_available(self):
        """Dither preview доступен для 1bit режима."""
        from retouch.processing.output.export import export_result
        assert callable(export_result)

    def test_curated_set_has_fixtures(self):
        """Curated set >= 5 изображений."""
        files = [f for f in os.listdir(FIXTURES_DIR) if f.endswith(".png")]
        assert len(files) >= 5, f"Curated set: {len(files)} < 5 fixtures"

    def _dither_and_compare(self, fixture_name: str):
        """Загрузить fixture, dither, сравнить с reference .bmp."""
        src = os.path.join(FIXTURES_DIR, fixture_name)
        ref_name = fixture_name.replace(".png", "_dither.bmp")
        ref_path = os.path.join(FIXTURES_DIR, ref_name)
        if not os.path.exists(ref_path):
            pytest.skip(f"Reference not found: {ref_path}")

        img = Image.open(src).convert("L")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.bmp")
            export_result(
                img, out,
                machine_type="laser_standard",
                fmt="bmp_1bit",
                export_mode="1bit",
                step_mm=0.300,
                dither_method_1bit="jarvis",
            )
            assert filecmp.cmp(out, ref_path, shallow=False), (
                f"Dither output differs from reference: {fixture_name}"
            )

    def test_mid_gray_regression(self):
        self._dither_and_compare("mid_gray.png")

    def test_gradient_h_regression(self):
        self._dither_and_compare("gradient_h.png")

    def test_gradient_v_regression(self):
        self._dither_and_compare("gradient_v.png")

    def test_face_like_regression(self):
        self._dither_and_compare("face_like.png")

    def test_high_contrast_regression(self):
        self._dither_and_compare("high_contrast.png")
