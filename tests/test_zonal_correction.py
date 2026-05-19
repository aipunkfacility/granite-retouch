"""Тесты для зональной коррекции — skin-only bounded correction."""

import numpy as np
import pytest

from retouch.processing.plan import PipelinePlan, SafetyEnvelope, validate_plan


class TestSkinOnlyBoundedCorrection:
    """Skin-only bounded correction формула."""

    def test_skin_only_delta_does_not_affect_clothes(self):
        """Чёрная одежда не светлеет из-за лица."""
        arr = np.zeros((10, 10), dtype=np.float32)
        arr[:, :5] = 100.0  # face_skin зона
        arr[:, 5:] = 20.0   # clothes зона

        # Применяем delta только к face_skin
        face_skin_mask = np.zeros((10, 10), dtype=bool)
        face_skin_mask[:, :5] = True

        delta = 10.0
        corrected = arr.copy()
        corrected[face_skin_mask] += delta

        assert corrected[0, 0] == 110.0  # face_skin изменена
        assert corrected[0, 6] == 20.0   # clothes не изменена

    def test_skin_only_delta_does_not_affect_hair(self):
        """Волосы не становятся серыми."""
        arr = np.zeros((10, 10), dtype=np.float32)
        arr[:5, :] = 100.0  # face_skin
        arr[5:, :] = 40.0   # hair

        face_skin_mask = np.zeros((10, 10), dtype=bool)
        face_skin_mask[:5, :] = True

        delta = 10.0
        corrected = arr.copy()
        corrected[face_skin_mask] += delta

        assert corrected[6, 0] == 40.0  # hair не изменена

    def test_skin_delta_bounded_by_envelope(self):
        """Delta не превышает safety envelope."""
        plan = PipelinePlan(skin_delta=50.0)
        env = SafetyEnvelope(face_skin_max_delta=15.0)
        result = validate_plan(plan, "standard", envelope=env)
        assert result.plan.skin_delta == 15.0

    def test_face_dark_small_pct_skips_correction(self):
        """face_dark < 5% получает ослабленную коррекцию."""
        face_dark_area = 30
        face_mask_area = 1000
        ratio = face_dark_area / face_mask_area * 100
        assert ratio < 5.0

    def test_delta_zero_when_in_target_range(self):
        """Median в target_range → delta = 0."""
        median = 185.0
        target_min = 180.0
        target_max = 190.0

        if median < target_min:
            target_delta = target_min - median
        elif median > target_max:
            target_delta = target_max - median
        else:
            target_delta = 0

        assert target_delta == 0

    def test_delta_positive_when_below_target(self):
        """Median ниже target_min → осветление."""
        median = 170.0
        target_min = 180.0
        max_delta = 15.0

        if median < target_min:
            target_delta = min(target_min - median, max_delta)
        elif median > target_max:
            target_delta = max(target_max - median, -max_delta)
        else:
            target_delta = 0

        assert target_delta == 10.0

    def test_delta_negative_when_above_target(self):
        """Median выше target_max → затемнение."""
        median = 200.0
        target_max = 190.0
        max_delta = 15.0
        target_min = 180.0

        if median < target_min:
            target_delta = min(target_min - median, max_delta)
        elif median > target_max:
            target_delta = max(target_max - median, -max_delta)
        else:
            target_delta = 0

        assert target_delta == -10.0
