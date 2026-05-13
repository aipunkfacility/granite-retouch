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
