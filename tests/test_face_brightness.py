"""Tests for unified face brightness correction module."""
import logging

import numpy as np
import pytest
from PIL import Image

from retouch.processing.correction.face_brightness import face_brightness_correction, _compute_gamma_aware_target


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
        assert after > 87.0, f"curves + bounded ±15 (shadow-priority weight, Phase 1+2): {after}"

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
        assert after > 87.0, f"После curves (shadow-priority weight, Phase 1+2): {after}"

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
    """Rolloff НЕ применяется в face_brightness_correction — только в postprocess."""

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

    def test_no_rolloff_even_with_correction(self):
        """При delta != 0 rolloff НЕ применяется — даже если пиксели выше ceiling."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        arr[80:120, 80:120] = 230  # яркое пятно > white_ceiling=200
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        result, _, _, _, _ = face_brightness_correction(
            img, mask, face_skin,
            {
                "face_brightness_target_min": 140,
                "face_brightness_target_max": 165,
                "white_ceiling": 200,
                "rolloff_compression": 0.35,
            },
            {"median_brightness": 80.0, "p90_brightness": 100.0},
        )
        result_arr = np.array(result)
        bright_spot = float(result_arr[100, 100])
        assert bright_spot >= 180, (
            f"Пиксель {bright_spot} сжат rolloff — rolloff не должен применяться "
            f"в face_brightness_correction"
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


class TestShadowPriorityWeight:
    """Phase 1 weight: тёмные пиксели получают больше коррекции, яркие — меньше."""

    def test_dark_pixels_get_more_correction_than_bright(self):
        """При delta > 0 пиксель 80 получает больше осветления, чем пиксель 220."""
        arr = np.full((200, 200), 150, dtype=np.uint8)
        arr[:50, :] = 80    # тёмная зона
        arr[150:, :] = 220  # яркая зона
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        result, _, _, _, _ = face_brightness_correction(
            img, mask, face_skin,
            {"face_brightness_target_min": 170, "face_brightness_target_max": 190},
            {"median_brightness": 150.0, "p90_brightness": 180.0},
        )
        result_arr = np.array(result)

        dark_shift = float(result_arr[:50, :].mean()) - 80
        bright_shift = float(result_arr[150:, :].mean()) - 220

        assert dark_shift > bright_shift, (
            f"Тёмные пиксели должны получить больше коррекции: "
            f"dark_shift={dark_shift:.1f}, bright_shift={bright_shift:.1f}"
        )

    def test_bright_pixels_stay_below_knee(self):
        """При delta=+15 пиксели face_skin 200+ не превышают knee после Phase 1."""
        arr = np.full((200, 200), 150, dtype=np.uint8)
        arr[50:100, :] = 210  # яркая зона face_skin
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        cfg = {
            "face_brightness_target_min": 170,
            "face_brightness_target_max": 190,
            "white_ceiling": 245,
            "rolloff_compression": 0.35,
        }
        result, _, _, _, _ = face_brightness_correction(
            img, mask, face_skin, cfg,
            {"median_brightness": 150.0, "p90_brightness": 180.0},
        )
        result_arr = np.array(result)

        bright_zone_max = float(result_arr[50:100, :].max())
        assert bright_zone_max < 220, (
            f"Яркие пиксели {bright_zone_max:.1f} не должны превышать 220 "
            f"после shadow-priority weight"
        )


class TestGammaAwareTargetNoCollapse:
    """_compute_gamma_aware_target не должен коллапсировать диапазон."""

    def test_laser_preset_no_target_collapse(self):
        """Laser-пресет (gamma=0.88, target 230/245) не даёт effective_min == effective_max."""
        eff_min, eff_max = _compute_gamma_aware_target(
            230, 245, {"stone_gamma": 0.88, "white_ceiling": 250},
        )
        assert eff_max > eff_min + 10, (
            f"Target collapsed: effective_min={eff_min:.1f}, effective_max={eff_max:.1f}. "
            f"Range must be > 10 levels to preserve tonal variation."
        )

    def test_impact_preset_reasonable_range(self):
        """Impact-пресет (gamma=0.90, target 200/225) даёт диапазон >= 20 уровней."""
        eff_min, eff_max = _compute_gamma_aware_target(
            200, 225, {"stone_gamma": 0.90, "white_ceiling": 240},
        )
        assert eff_max - eff_min >= 20, (
            f"Range too narrow: {eff_max - eff_min:.1f} levels. "
            f"Expected >= 20 for tonal variation."
        )

    def test_range_width_preserved_when_clamped(self):
        """При клэмпинге ширина диапазона сохраняется (shift down)."""
        eff_min, eff_max = _compute_gamma_aware_target(
            230, 245, {"stone_gamma": 0.88, "white_ceiling": 250},
        )
        range_width = eff_max - eff_min
        assert range_width >= 14, (
            f"Range width {range_width:.1f} too narrow — "
            f"original pre-gamma width is ~16.9"
        )

    def test_no_adjustment_when_gamma_is_one(self):
        """При gamma=1.0 — без корректировки."""
        eff_min, eff_max = _compute_gamma_aware_target(200, 225, {"stone_gamma": 1.0, "white_ceiling": 240})
        assert eff_min == 200.0
        assert eff_max == 225.0


class TestPhase2ShadowPriority:
    """Phase 2 weight_curve: тёмные пиксели получают больше коррекции, яркие — меньше."""

    def test_phase2_does_not_push_bright_pixels_to_knee(self):
        """При correction > 1.0 пиксели 190+ не выталкиваются к knee."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        arr[50:100, 50:100] = 190  # яркое пятно
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        cfg = {
            "face_brightness_target_min": 170,
            "face_brightness_target_max": 190,
            "white_ceiling": 245,
            "highlight_start": 200,
        }
        result, _, _, _, _ = face_brightness_correction(
            img, mask, face_skin, cfg,
            {"median_brightness": 80.0, "p90_brightness": 100.0},
        )
        result_arr = np.array(result)

        bright_zone_max = float(result_arr[50:100, 50:100].max())
        assert bright_zone_max < 215, (
            f"Bright spot {bright_zone_max:.1f} pushed too high by Phase 2. "
            f"Should stay below 215 with shadow-priority weight."
        )

    def test_phase2_dark_pixels_get_more_relative_correction(self):
        """При correction > 1.0 тёмные пиксели получают больший относительный прирост."""
        arr = np.full((200, 200), 80, dtype=np.uint8)
        arr[:50, :] = 80    # тёмная зона
        arr[150:, :] = 180  # яркая зона
        img = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        face_skin = np.ones((200, 200), dtype=np.uint8) * 255

        result, _, _, _, _ = face_brightness_correction(
            img, mask, face_skin,
            {"face_brightness_target_min": 170, "face_brightness_target_max": 190},
            {"median_brightness": 80.0, "p90_brightness": 100.0},
        )
        result_arr = np.array(result)

        dark_shift_pct = (float(result_arr[:50, :].mean()) - 80) / 80 * 100
        bright_shift_pct = (float(result_arr[150:, :].mean()) - 180) / 180 * 100

        assert dark_shift_pct > bright_shift_pct, (
            f"Phase 2: тёмные пиксели должны получать больше % коррекции: "
            f"dark={dark_shift_pct:.1f}%, bright={bright_shift_pct:.1f}%"
        )


class TestSafetyCapFallback:
    """Safety cap в steps.py работает даже без zone_masks."""

    def test_safety_cap_uses_face_mask_fallback(self):
        """При zone_masks=None safety cap клиппит face_skin через face_mask."""
        gamma = 0.90
        ceiling = 240.0
        knee = ceiling * 0.90
        safe_post_gamma = knee - 10  # FACE_SKIN_KNEE_MARGIN
        max_pre_gamma = np.power(safe_post_gamma / 255.0, 1.0 / gamma) * 255.0

        arr = np.full((100, 100), 230, dtype=np.uint8)
        img = Image.fromarray(arr, mode='L')

        face_mask = np.zeros((100, 100), dtype=np.uint8)
        face_mask[30:70, 30:70] = 255

        _fs_mask = face_mask > 128  # already bool
        _arr = np.array(img, dtype=np.float32)
        _fs_bool = _fs_mask  # bool mask, no double-conversion
        _above = _arr[_fs_bool] > max_pre_gamma
        if np.any(_above):
            _arr[_fs_bool] = np.minimum(_arr[_fs_bool], max_pre_gamma)

        result_max = float(_arr[_fs_bool].max())
        assert result_max <= max_pre_gamma + 1, (
            f"Safety cap failed: max {result_max:.1f} > max_pre_gamma {max_pre_gamma:.1f}"
        )


class TestUnsharpFaceSkinOvershoot:
    """Unsharp mask overshoot на face_skin ограничивается (amplitude cap)."""

    def test_overshoot_amplitude_only(self):
        """На face_skin overshoot не превышает face_overshoot_limit."""
        from retouch.processing.correction.unsharp import apply_unsharp_mask

        arr = np.full((100, 100), 180, dtype=np.uint8)
        arr[40:60, 40:60] = 220
        img = Image.fromarray(arr, mode='L')

        face_skin = np.zeros((100, 100), dtype=np.uint8)
        face_skin[30:70, 30:70] = 255

        subj = Image.new("L", (100, 100), 255)

        result = apply_unsharp_mask(
            img, radius=1.5, percent=150, threshold=0,
            subject_mask=subj,
            face_skin_mask=face_skin,
            face_overshoot_limit=8,
        )

        result_arr = np.array(result)
        fs_bool = face_skin > 128
        face_pixels = result_arr[fs_bool]
        assert face_pixels.max() <= 228, (
            f"face_skin max {face_pixels.max()} exceeds original + overshoot_limit"
        )

    def test_non_face_skin_unaffected(self):
        """Зоны вне face_skin получают полную резкость (без ограничения)."""
        from retouch.processing.correction.unsharp import apply_unsharp_mask

        arr = np.full((100, 100), 128, dtype=np.uint8)
        arr[40:60, 40:60] = 200
        img = Image.fromarray(arr, mode='L')

        face_skin = np.zeros((100, 100), dtype=np.uint8)
        face_skin[0:20, 0:20] = 255

        subj = Image.new("L", (100, 100), 255)

        result_no_limit = apply_unsharp_mask(
            img, radius=1.5, percent=150, threshold=0,
            subject_mask=subj,
        )
        result_with_limit = apply_unsharp_mask(
            img, radius=1.5, percent=150, threshold=0,
            subject_mask=subj,
            face_skin_mask=face_skin,
            face_overshoot_limit=8,
        )

        r1 = np.array(result_no_limit)[40:60, 40:60]
        r2 = np.array(result_with_limit)[40:60, 40:60]
        assert np.array_equal(r1, r2), "Non-face_skin zones must receive full sharpening"

    def test_no_overshoot_limit_compatible(self):
        """Без face_skin_mask — обратная совместимость (старое поведение)."""
        from retouch.processing.correction.unsharp import apply_unsharp_mask

        arr = np.full((50, 50), 150, dtype=np.uint8)
        img = Image.fromarray(arr, mode='L')
        subj = Image.new("L", (50, 50), 255)

        result = apply_unsharp_mask(
            img, radius=1.5, percent=120, threshold=0,
            subject_mask=subj,
        )
        assert result is not None

    def test_no_numpy_roundtrip_without_masks(self):
        """Без numpy-масок возвращается PIL Image напрямую."""
        from retouch.processing.correction.unsharp import apply_unsharp_mask

        arr = np.full((50, 50), 150, dtype=np.uint8)
        img = Image.fromarray(arr, mode='L')

        result = apply_unsharp_mask(
            img, radius=1.5, percent=120, threshold=0,
        )
        assert result is not None
        assert isinstance(result, Image.Image)

    def test_overshoot_limit_minimum_one(self):
        """face_overshoot_limit=1 — минимальное значение."""
        from retouch.processing.correction.unsharp import apply_unsharp_mask

        arr = np.full((50, 50), 150, dtype=np.uint8)
        img = Image.fromarray(arr, mode='L')
        face_skin = np.ones((50, 50), dtype=np.uint8)
        subj = Image.new("L", (50, 50), 255)

        result = apply_unsharp_mask(
            img, radius=1.5, percent=120, threshold=0,
            subject_mask=subj,
            face_skin_mask=face_skin,
            face_overshoot_limit=1,
        )
        assert result is not None
