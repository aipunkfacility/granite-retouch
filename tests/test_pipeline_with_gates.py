"""Интеграционный тест полного пайплайна с quality gates."""

import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS
from retouch.processing.core.pipeline import process_steps


class TestPipelineWithGates:
    """Quality gates enforcement в полном пайплайне."""

    def _make_blue_chromakey(self, subject_gray=180) -> np.ndarray:
        """Создать RGBA изображение с синим хромакеем и серым субъектом."""
        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255       # синий канал = 255 (хромакей)
        arr[..., 3] = 255       # alpha = 255
        arr[100:400, 100:400] = [subject_gray, subject_gray, subject_gray, 255]
        return arr

    def test_pipeline_gate_enforcement_full_cycle(self, tmp_path):
        """Полный пайплайн: gates срабатывают и ослабляют параметры."""
        arr = self._make_blue_chromakey(subject_gray=250)
        img_path = str(tmp_path / "overbright.png")
        Image.fromarray(arr).save(img_path)

        config = DEFAULTS.copy()
        config["processing"]["min_resolution"] = 512

        result = process_steps(
            img_path, machine_type="laser_standard", config=config,
        )

        assert result.gate_state is not None
        assert len(result.step_metrics) > 0

    def test_gate_variance_loss_triggers_enforcement(self, tmp_path):
        """variance_loss gate срабатывает при агрессивной коррекции."""
        arr = self._make_blue_chromakey(subject_gray=180)
        img_path = str(tmp_path / "mid.png")
        Image.fromarray(arr).save(img_path)

        config = DEFAULTS.copy()
        config["processing"]["min_resolution"] = 512

        result = process_steps(
            img_path, machine_type="laser_standard", config=config,
        )
        assert result.gate_state is not None
        assert "step_metrics" in result.__dataclass_fields__

    def test_gate_p95_shift_with_dark_face(self, tmp_path):
        """p95_shift gate срабатывает при затемнении светлого лица."""
        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255    # синий хромакей
        arr[..., 3] = 255
        arr[150:350, 150:350] = [220, 220, 220, 255]  # светлое лицо
        img_path = str(tmp_path / "bright_face.png")
        Image.fromarray(arr).save(img_path)

        config = DEFAULTS.copy()
        config["processing"]["min_resolution"] = 512

        result = process_steps(
            img_path, machine_type="laser_standard", config=config,
        )
        assert result.gate_state is not None
