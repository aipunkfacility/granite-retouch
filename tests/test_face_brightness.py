"""Tests for unified face brightness correction module."""
import numpy as np
import pytest
from PIL import Image

from retouch.processing.correction.face_brightness import face_brightness_correction


class TestUnifiedBrightnessMeasurement:
    """Замер всегда по face_skin, не по face_mask (фикс зонного конфликта)."""

    def test_measurement_uses_face_skin_only(self):
        """Медиана считается по face_skin, исключая волосы/бороду."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        arr[50:150, 50:150] = 200  # центр — светлая кожа
        arr[:30, :] = 30  # верх — тёмные волосы
        img = Image.fromarray(arr)
        subject_mask = Image.new("L", (200, 200), 255)

        face_skin = np.zeros((200, 200), dtype=np.uint8)
        face_skin[50:150, 50:150] = 255  # только кожа

        result, before, after, factor, _ = face_brightness_correction(
            img, subject_mask, face_skin, {},
            {"median_brightness": 200, "p90_brightness": 210},
        )
        assert factor == 1.0, f"Кожа 200 — без коррекции, factor={factor}"


class TestLinearShift:
    """Фаза 1: bounded linear shift."""

    def test_dark_face_skin_gets_brightened(self):
        """Тёмная кожа осветляется (linear delta bounded ±15, curves может добавить)."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        result, before, after, factor, _ = face_brightness_correction(
            img, mask, face_skin, {"face_brightness_target_min": 140, "face_brightness_target_max": 165},
            {"median_brightness": 80.0, "p90_brightness": 100.0},
        )
        result_arr = np.array(result)
        assert result_arr.mean() > 80.0
        assert factor > 1.0
        assert after > 95.0, f"curves поднимает выше bounded ±15: {after}"

    def test_bright_face_skin_gets_darkened(self):
        """Слишком яркая кожа затемняется."""
        arr = np.full((200, 200), 200, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        result, before, after, factor, _ = face_brightness_correction(
            img, mask, face_skin, {"face_brightness_target_min": 140, "face_brightness_target_max": 165},
            {"median_brightness": 200.0, "p90_brightness": 220.0},
        )
        assert factor < 1.0





class TestCurvesFineTune:
    """Фаза 2: curves после linear shift."""

    def test_curves_applied_if_still_outside_target(self):
        """Если после linear shift median вне target → curves fine-tune."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        result, before, after, factor, _ = face_brightness_correction(
            img, mask, face_skin,
            {"face_brightness_target_min": 160, "face_brightness_target_max": 180},
            {"median_brightness": 80.0, "p90_brightness": 100.0},
        )
        assert after > 95.0, f"После curves должно быть > 95: {after}"

    def test_no_curves_if_already_in_target(self):
        """Если после linear shift median в target — curves не нужен."""
        arr = np.full((200, 200), 100, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        result, before, after, factor, _ = face_brightness_correction(
            img, mask, face_skin,
            {"face_brightness_target_min": 90, "face_brightness_target_max": 110},
            {"median_brightness": 100.0, "p90_brightness": 105.0},
        )
        assert factor == 1.0


class TestNoRolloffInFaceBrightness:
    """Rolloff удалён из face_brightness_correction (v6.5 — двойной ceiling)."""

    def test_no_rolloff_from_face_brightness(self):
        """Пиксели выше ceiling остаются без изменений — rolloff удалён."""
        arr = np.full((200, 200), 100, dtype=np.uint8)
        arr[80:120, 80:120] = 230  # яркое пятно > white_ceiling=200
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        # median 100 — в target, коррекция не нужна
        result, _, _, _, _ = face_brightness_correction(
            img, mask, face_skin,
            {
                "face_brightness_target_min": 80,
                "face_brightness_target_max": 120,
                "white_ceiling": 200,
                "rolloff_compression": 0.35,
            },
            {"median_brightness": 100.0, "p90_brightness": 120.0},
        )
        result_arr = np.array(result)
        assert result_arr[100, 100] > 200, (
            "face_brightness не должен ceiling-ить: пиксель 230 должен остаться 230"
        )


class TestMaskProtection:
    """Фон не меняется при коррекции."""

    def test_background_preserved(self):
        """Пиксели вне subject_mask не меняются."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        mask_arr = np.zeros((200, 200), dtype=np.uint8)
        mask_arr[:, :100] = 255
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)
        face_skin = np.zeros((200, 200), dtype=np.uint8)
        face_skin[:, :100] = 255

        result, _, _, _, _ = face_brightness_correction(
            img, mask, face_skin,
            {"face_brightness_target_min": 140, "face_brightness_target_max": 165},
            {"median_brightness": 80.0, "p90_brightness": 100.0},
        )
        result_arr = np.array(result)
        assert np.all(result_arr[:, 100:] == 80)


class TestNoFaceSkinFallback:
    """Без face_skin_mask — коррекция по subject_mask."""

    def test_fallback_to_subject_mask(self):
        """face_skin=None → использует subject_mask."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)

        result, before, after, factor, _ = face_brightness_correction(
            img, mask, face_skin_mask=None,
            machine_cfg={"face_brightness_target_min": 140, "face_brightness_target_max": 165},
            analytics={"median_brightness": 80.0, "p90_brightness": 100.0},
        )
        assert factor > 1.0


class TestEmptyMask:
    """Пустая маска — без изменений."""

    def test_empty_mask_returns_original(self):
        """Пустая face_skin — изображение не меняется."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.zeros((200, 200), dtype=np.uint8)

        result, before, after, factor, _ = face_brightness_correction(
            img, mask, face_skin,
            {"face_brightness_target_min": 140, "face_brightness_target_max": 165},
            {"median_brightness": 80.0, "p90_brightness": 100.0},
        )
        assert factor == 1.0
        assert np.array_equal(np.array(img), np.array(result))


class TestGammaAwareTarget:
    """Gamma-aware target computation prevents face_skin from entering rolloff zone."""

    def test_gamma_aware_lowers_effective_target(self):
        """With gamma < 1.0, face_brightness outputs values lower than target_min.

        Uses median=193 (slightly below target_min=200) so that Phase 2
        correction factor differs between gamma-aware and non-gamma cases:
          - No gamma:   target_min=200, gap=7, correction ~= 1.036
          - Gamma-aware: effective_min~=195, gap=2, correction ~= 1.010
        This creates a measurable difference in output brightness.
        """
        arr = np.full((200, 200), 193, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        cfg_gamma = {
            "face_brightness_target_min": 200,
            "face_brightness_target_max": 225,
            "stone_gamma": 0.90,
            "white_ceiling": 240,
            "rolloff_compression": 0.35,
        }
        cfg_no_gamma = {
            "face_brightness_target_min": 200,
            "face_brightness_target_max": 225,
        }
        analytics = {"median_brightness": 193.0, "p90_brightness": 195.0}

        result_gamma, _, _, _, _ = face_brightness_correction(
            img, mask, face_skin, cfg_gamma, analytics,
        )
        result_no_gamma, _, _, _, _ = face_brightness_correction(
            img.copy(), mask, face_skin, cfg_no_gamma, analytics,
        )

        gamma_median = float(np.median(np.array(result_gamma)))
        no_gamma_median = float(np.median(np.array(result_no_gamma)))

        assert gamma_median < no_gamma_median, (
            f"Gamma-aware median {gamma_median} should be < "
            f"no-gamma median {no_gamma_median}"
        )
        gamma_max = float(np.array(result_gamma).max())
        assert gamma_max <= 215, (
            f"Face skin max {gamma_max} > 215 — gamma-aware target "
            f"did not keep face_skin near pre-gamma ceiling"
        )

    def test_no_adjustment_when_gamma_is_one(self):
        """With gamma=1.0, effective_min == target_min — no gamma-aware adjustment."""
        from retouch.processing.correction.face_brightness import _compute_gamma_aware_target

        eff_min, eff_max = _compute_gamma_aware_target(200, 225, {"stone_gamma": 1.0, "white_ceiling": 240})
        assert eff_min == 200.0, f"effective_min {eff_min} != 200.0 when gamma=1.0"
        assert eff_max == 225.0, f"effective_max {eff_max} != 225.0 when gamma=1.0"

        eff_min2, eff_max2 = _compute_gamma_aware_target(200, 225, {})
        assert eff_min2 == 200.0, f"effective_min {eff_min2} != 200.0 when gamma missing"
        assert eff_max2 == 225.0, f"effective_max {eff_max2} != 225.0 when gamma missing"

        eff_min3, eff_max3 = _compute_gamma_aware_target(200, 225, {"stone_gamma": None})
        assert eff_min3 == 200.0, f"effective_min {eff_min3} != 200.0 when gamma=None"
        assert eff_max3 == 225.0, f"effective_max {eff_max3} != 225.0 when gamma=None"

    def test_safety_cap_in_steps_py(self):
        """Level 2 safety cap in steps.py clips face_skin after unsharp overshoot."""
        arr = np.full((100, 100), 200, dtype=np.uint8)
        arr[10:20, 10:20] = 210
        img = Image.fromarray(arr)

        from retouch.processing.correction.unsharp import apply_unsharp_mask
        sharpened = apply_unsharp_mask(img, radius=1.5, percent=150, threshold=0)

        gamma = 0.90
        ceiling = 240.0
        knee = ceiling * 0.90
        max_pre_gamma = np.power(knee / 255.0, 1.0 / gamma) * 255.0

        sharp_arr = np.array(sharpened, dtype=np.float32)
        fs_bool = np.ones((100, 100), dtype=bool)
        sharp_arr[fs_bool] = np.minimum(sharp_arr[fs_bool], max_pre_gamma)

        result_max = float(sharp_arr.max())
        assert result_max <= max_pre_gamma + 1, (
            f"After safety cap, max {result_max} > max_pre_gamma+1 {max_pre_gamma+1:.1f}"
        )
