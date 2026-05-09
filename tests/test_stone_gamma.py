"""Тесты stone_gamma и удаления brightness (FIX #1, #8).

TDD Red-Green-Refactor:
  Red: тесты падают — подтверждают баг (brightness гасит осветление)
  Green: минимальный фикс — тесты проходят
  Refactor: чистка
"""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.levels import (
    apply_levels,
    _adaptive_levels_factor,
)


class TestAdaptiveLevelsBrightnessRemoved:
    """FIX #1: brightness больше не влияет на adaptive factor."""

    def test_brightness_param_ignored_in_adaptive(self):
        """При adaptive-режиме brightness из machine_cfg НЕ используется."""
        analytics = {'median_brightness': 80.0, 'p90_brightness': 150.0}
        # С brightness=0.85 — фактор должен быть как без него
        factor_with = _adaptive_levels_factor(
            analytics, 'laser_80w',
            machine_cfg={"brightness": 0.85, "target_pre_fb": 150})
        factor_without = _adaptive_levels_factor(
            analytics, 'laser_80w',
            machine_cfg={"target_pre_fb": 150})
        assert factor_with == factor_without, \
            f"brightness не должен влиять: {factor_with} vs {factor_without}"

    def test_dark_face_always_brightened_for_laser_80w(self):
        """Тёмное лицо (median=80) для laser_80w получает factor > 1.0."""
        analytics = {'median_brightness': 80.0, 'p90_brightness': 150.0}
        factor = _adaptive_levels_factor(
            analytics, 'laser_80w',
            machine_cfg={"target_pre_fb": 150})
        assert factor > 1.0, \
            f"laser_80w: тёмное лицо должно осветляться, factor={factor:.3f}"

    def test_dark_face_always_brightened_all_machines(self):
        """Тёмное лицо (median=80) для всех машин получает factor > 1.0."""
        analytics = {'median_brightness': 80.0, 'p90_brightness': 150.0}
        for machine in ['laser_standard', 'laser_80w', 'impact']:
            factor = _adaptive_levels_factor(analytics, machine)
            assert factor > 1.0, \
                f"{machine}: тёмное лицо должно осветляться, factor={factor:.3f}"

    def test_single_clamp_range(self):
        """Фактор ограничен одним диапазоном [0.50, 1.50]."""
        # Очень тёмное изображение → factor огромный → clamp до 1.50
        analytics = {'median_brightness': 1.0, 'p90_brightness': 10.0}
        factor = _adaptive_levels_factor(analytics, 'laser_80w')
        assert 0.50 <= factor <= 1.50

    def test_very_bright_input_factor_below_one(self):
        """Яркий вход (median=240) даёт factor < 1.0."""
        analytics = {'median_brightness': 240.0, 'p90_brightness': 250.0}
        factor = _adaptive_levels_factor(analytics, 'laser_standard')
        assert factor < 1.0, "Яркий вход должен затемняться к target"


class TestStoneGammaCorrection:
    """FIX #8: gamma-коррекция для компенсации потемнения на камне."""

    def test_gamma_below_one_brightens_shadows(self):
        """Gamma < 1.0 поднимает тени (SOP 5.1)."""
        from retouch.processing.gamma import apply_stone_gamma
        arr = np.array([30, 80, 128, 200, 250], dtype=np.float32)
        result = apply_stone_gamma(arr, gamma=0.85)
        # Тени подняты
        assert result[0] > 30, f"Тень должна быть поднята: {result[0]:.0f}"
        assert result[1] > 80, f"Средняя тень поднята: {result[1]:.0f}"
        # Белая точка почти не сдвинулась
        assert result[4] >= 248, f"Белая точка стабильна: {result[4]:.0f}"

    def test_gamma_1_is_identity(self):
        """Gamma=1.0 — нейтральная (ничего не меняется)."""
        from retouch.processing.gamma import apply_stone_gamma
        arr = np.array([50, 128, 200], dtype=np.float32)
        result = apply_stone_gamma(arr, gamma=1.0)
        np.testing.assert_array_almost_equal(result, arr, decimal=1)

    def test_gamma_only_inside_mask(self):
        """Gamma применяется только внутри маски субъекта."""
        from retouch.processing.gamma import apply_stone_gamma_masked
        arr = np.full((100, 100), 80, dtype=np.float32)
        mask = np.zeros((100, 100), dtype=bool)
        mask[25:75, 25:75] = True  # субъект — квадрат в центре
        result = apply_stone_gamma_masked(arr, mask, gamma=0.85)
        # Вне маски — не изменилось
        assert result[10, 10] == 80.0, "Фон не должен меняться"
        # Внутри маски — поднялось
        assert result[50, 50] > 80.0, "Субъект должен осветлиться"

    def test_gamma_preserves_range(self):
        """Результат gamma в [0, 255]."""
        from retouch.processing.gamma import apply_stone_gamma
        arr = np.array([0, 1, 127, 255], dtype=np.float32)
        result = apply_stone_gamma(arr, gamma=0.80)
        assert result.min() >= 0 and result.max() <= 255

    def test_gamma_monotonic(self):
        """Gamma сохраняет монотонность: если a < b то gamma(a) < gamma(b)."""
        from retouch.processing.gamma import apply_stone_gamma
        arr = np.array([10, 50, 100, 150, 200, 240], dtype=np.float32)
        result = apply_stone_gamma(arr, gamma=0.85)
        for i in range(len(result) - 1):
            assert result[i] < result[i + 1], \
                f"Нарушена монотонность: gamma({arr[i]:.0f})={result[i]:.1f} >= gamma({arr[i+1]:.0f})={result[i+1]:.1f}"


class TestLaser80wConfigRestored:
    """FIX #2: laser_80w параметры восстановлены к DEFAULTS."""

    def test_target_pre_fb_not_below_150(self):
        """target_pre_fb для laser_80w >= 150 (не 120)."""
        from retouch.config import load_config
        config = load_config()
        assert config["processing"]["laser_80w"]["target_pre_fb"] >= 150

    def test_face_target_min_not_below_190(self):
        """face_brightness_target_min для laser_80w >= 190."""
        from retouch.config import load_config
        config = load_config()
        assert config["processing"]["laser_80w"]["face_brightness_target_min"] >= 190

    def test_white_ceiling_not_below_235(self):
        """white_ceiling для laser_80w >= 235."""
        from retouch.config import load_config
        config = load_config()
        assert config["processing"]["laser_80w"]["white_ceiling"] >= 235

    def test_no_brightness_key(self):
        """Параметр brightness удалён из конфига."""
        from retouch.config import load_config
        config = load_config()
        for machine in ("laser_standard", "laser_80w", "impact"):
            assert "brightness" not in config["processing"][machine], \
                f"{machine}: brightness должен быть удалён"

    def test_stone_gamma_present(self):
        """stone_gamma указан для всех машин."""
        from retouch.config import load_config
        config = load_config()
        for machine in ("laser_standard", "laser_80w", "impact"):
            assert "stone_gamma" in config["processing"][machine], \
                f"{machine}: нет stone_gamma"
            assert 0.75 <= config["processing"][machine]["stone_gamma"] <= 1.0


class TestVignetteOffsetRestored:
    """FIX #3: vertical_offset не обрезает треть портрета."""

    def test_vertical_offset_le_015(self):
        """vertical_offset <= 0.15 в конфиге."""
        from retouch.config import load_config
        config = load_config()
        assert config["vignette"]["vertical_offset"] <= 0.15

    def test_vignette_preserves_lower_portion(self):
        """Нижние 20% изображения не зачернены полностью."""
        from retouch.processing.vignette import generate_arch_mask
        from retouch.config import load_config
        config = load_config()
        vign_cfg = config["vignette"]
        mask = generate_arch_mask(300, 400, vign_cfg)
        arr = np.array(mask)
        # Нижние 20% (rows 320-399) должны иметь видимость
        lower_20 = arr[320:, :]
        visible = (lower_20 > 128).sum() / lower_20.size
        assert visible > 0.20, \
            f"Нижние 20% слишком зачернены: {visible:.0%} видимости"
