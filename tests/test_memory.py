"""Тесты потребления памяти полным пайплайном."""

import tracemalloc

import numpy as np
import pytest
from PIL import Image


def _make_test_image(size=1024):
    """Создать тестовое изображение size×size с синим хромакеем и лицом."""
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    # Синий фон (хромакей)
    arr[..., 2] = 255
    arr[..., 3] = 255
    # «Лицо» — светлый прямоугольник в центре
    margin = size // 4
    arr[margin:size - margin, margin:size - margin] = [200, 200, 200, 255]
    return Image.fromarray(arr)


class TestPipelineMemory:
    """Проверка что полный пайплайн не уходит в OOM."""

    @pytest.mark.slow
    @pytest.mark.parametrize("machine_type", [
        "laser_standard",
        "laser_80w",
        "impact",
    ])
    def test_pipeline_memory_per_profile(self, machine_type, tmp_path):
        """Полный пайплайн на 1024×1024 — пик памяти < 500 MB.

        1024×1024×4 канала = 4 MB. Пайплайн создаёт ~10-15 промежуточных
        массивов + scipy буферы. Реалистичный пик ~50-200 MB.
        Порог 500 MB — щедрый, но ловит OOM-регрессию.
        """
        import gc

        from retouch.processing.pipeline import process_export
        from retouch.config import DEFAULTS

        # T-F2: ensure tracemalloc is stopped and GC runs between tests
        tracemalloc.stop()
        gc.collect()

        img = _make_test_image(1024)
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.bmp"
        img.save(str(input_path))

        config = DEFAULTS.copy()
        # Увеличить min_resolution чтобы пройти валидацию
        config["processing"]["min_resolution"] = 512

        tracemalloc.start()
        try:
            process_export(
                str(input_path),
                str(output_path),
                machine_type=machine_type,
                config=config,
            )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            gc.collect()

        peak_mb = peak / 1e6
        assert peak < 500_000_000, (
            f"Пиковое потребление памяти {machine_type} аномально высокое: "
            f"{peak_mb:.1f} MB (порог 500 MB)"
        )

    def test_max_resolution_4096_accepted(self, tmp_path):
        """Изображение 4096×4096 не должно отклоняться валидацией."""
        from retouch.validation.image import validate_image_input
        from retouch.config import DEFAULTS

        img = Image.new("RGBA", (4096, 4096), (0, 0, 255, 255))
        path = tmp_path / "big.png"
        img.save(str(path))

        config = DEFAULTS.copy()
        # Должно пройти — max_resolution=4096 в DEFAULTS
        assert validate_image_input(str(path), config) is True


class TestZoneMasksMemory8K:
    """Проверка что ZoneMasks на 8K не превышает budget.

    План: 800 MB для 7680×4320 single-pass.
    Каждая uint8 маска: 7680×4320 = 33.2 MB.
    9 масок = ~300 MB + grayscale + рабочие массивы.
    Реальный пик ~1 GB из-за промежуточных numpy операций.
    """

    def test_zone_masks_memory_8k(self):
        """ZoneMasks на 8K (7680×4320) — пик < 1200 MB."""
        import gc
        import tracemalloc

        from retouch.processing.zones import build_zone_masks

        gc.collect()
        tracemalloc.stop()

        # Создаём synthetic masks для 8K
        width, height = 7680, 4320

        # Subject mask — эллипс в центре
        subj_arr = np.zeros((height, width), dtype=np.uint8)
        cy, cx = height // 2, width // 2
        ry, rx = height // 3, width // 4
        y_idx, x_idx = np.ogrid[:height, :width]
        ellipse = ((x_idx - cx) / rx) ** 2 + ((y_idx - cy) / ry) ** 2 <= 1.0
        subj_arr[ellipse] = 255
        subject_mask = Image.fromarray(subj_arr, mode='L')

        # Face mask — эллипс поменьше
        face_arr = np.zeros((height, width), dtype=np.uint8)
        fy, fx = height // 2 - 100, width // 2
        fry, frx = height // 6, width // 8
        face_ellipse = ((x_idx - fx) / frx) ** 2 + ((y_idx - fy) / fry) ** 2 <= 1.0
        face_arr[face_ellipse] = 255
        face_mask = Image.fromarray(face_arr, mode='L')

        # Grayscale — synthetic
        gray_arr = np.full((height, width), 150, dtype=np.uint8)
        img_gray = Image.fromarray(gray_arr, mode='L')

        tracemalloc.start()
        try:
            zones = build_zone_masks(subject_mask, face_mask, img_gray)
            _, peak = tracemalloc.get_traced_memory()
            # Save zone sums before deletion
            face_skin_sum = np.sum(zones.face_skin)
            clothes_sum = np.sum(zones.clothes)
        finally:
            tracemalloc.stop()
            gc.collect()

        peak_mb = peak / 1e6
        assert peak < 1_200_000_000, (
            f"ZoneMasks на 8K аномально высокое: {peak_mb:.1f} MB (порог 1200 MB)"
        )

        # Verify zones are not empty
        assert face_skin_sum > 0, "face_skin mask is empty"
        assert clothes_sum > 0, "clothes mask is empty"
