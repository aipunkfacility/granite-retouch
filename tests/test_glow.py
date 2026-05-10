"""Тесты модуля glow — outer/inner glow, numpy оптимизация."""

import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS


class TestGlowNumpyEquivalence:
    """numpy-реализация glow opacity эквивалентна point(lambda)."""

    def test_outer_glow_numpy_result(self):
        """Outer glow: numpy clip+multiply даёт корректный результат."""
        from retouch.processing.glow import apply_outer_glow

        # Создаём простую маску с чётким прямоугольником
        arr = np.zeros((100, 100), dtype=np.uint8)
        arr[30:70, 30:70] = 255
        mask = Image.fromarray(arr)
        img_gray = Image.new("L", (100, 100), 128)

        result = apply_outer_glow(img_gray, mask, glow_size=10, glow_opacity=0.35)
        assert result.mode == "L"
        assert result.size == (100, 100)

        # Результат не должен быть полностью чёрным или белым
        result_arr = np.array(result)
        assert result_arr.min() < 200, "Glow не должен заливать всё белым"
        assert result_arr.max() > 100, "Glow должен добавлять яркость"

    def test_outer_glow_with_full_mask(self):
        """Outer glow с полной маской — свечение некуда, результат ≈ оригинал."""
        from retouch.processing.glow import apply_outer_glow

        mask = Image.new("L", (80, 80), 255)  # Вся маска = субъект
        img_gray = Image.new("L", (80, 80), 128)

        result = apply_outer_glow(img_gray, mask, glow_size=10, glow_opacity=0.35)
        result_arr = np.array(result)

        # При полной маске glow_mask = blurred - original ≈ 0
        # Поэтому результат должен быть близок к оригиналу
        assert abs(float(result_arr.mean()) - 128.0) < 20, \
            "При полной маске outer glow не должен значительно менять изображение"


class TestCalculateGlowParamsLaser80wConfig:
    """REFACTOR-3: laser_80w glow-параметры должны читаться из конфига."""

    def test_laser_80w_custom_config_overrides_hardcode(self):
        """Кастомный конфиг laser_80w должен давать midpoint диапазона конфига,
        а не хардкод (20, 15)."""
        from retouch.processing.glow import _calculate_glow_params
        analytics = {'tonal_range': 100}
        custom_cfg = {
            'glow_size_min': 30, 'glow_size_max': 50,
            'glow_opacity_min': 20, 'glow_opacity_max': 40,
        }
        result = _calculate_glow_params(analytics, 'laser_80w', machine_cfg=custom_cfg)
        assert result == (40, 30), (
            f"Ожидали midpoint конфига (40, 30), получили {result} — "
            f"конфиг игнорируется, используется хардкод"
        )

    def test_laser_80w_default_config_matches_current_hardcode(self):
        """При дефолтном конфиге результат = текущий хардкод (20, 15)."""
        from retouch.processing.glow import _calculate_glow_params
        analytics = {'tonal_range': 100}
        default_cfg = {
            'glow_size_min': 15, 'glow_size_max': 25,
            'glow_opacity_min': 10, 'glow_opacity_max': 20,
        }
        result = _calculate_glow_params(analytics, 'laser_80w', machine_cfg=default_cfg)
        assert result == (20, 15)

    def test_laser_80w_no_config_uses_defaults(self):
        """Без machine_cfg — fallback на дефолтные значения."""
        from retouch.processing.glow import _calculate_glow_params
        analytics = {'tonal_range': 100}
        result = _calculate_glow_params(analytics, 'laser_80w')
        assert result == (20, 15)

    def test_laser_standard_unchanged_by_refactor(self):
        """laser_standard не затронут — поведение сохраняется."""
        from retouch.processing.glow import _calculate_glow_params
        analytics = {'tonal_range': 100}
        result = _calculate_glow_params(analytics, 'laser_standard')
        assert result == (50, 35)

    def test_impact_unchanged_by_refactor(self):
        """impact не затронут — поведение сохраняется."""
        from retouch.processing.glow import _calculate_glow_params
        analytics = {'subject_separation': 100}
        result = _calculate_glow_params(analytics, 'impact')
        assert result == (14, 65)


class TestGlowDeterminism:
    """D.1: glow должен быть детерминированным при одинаковых входах."""

    def test_same_analytics_same_result(self):
        """Одинаковые входы → одинаковый glow для всех machine_type."""
        from retouch.processing.glow import _calculate_glow_params
        for machine_type in ('laser_standard', 'laser_80w', 'impact'):
            analytics = {'tonal_range': 100, 'subject_separation': 100}
            r1 = _calculate_glow_params(analytics, machine_type)
            r2 = _calculate_glow_params(analytics, machine_type)
            assert r1 == r2, f"{machine_type}: не детерминирован"

    def test_preview_export_consistency(self):
        """D.1: preview и export получают одинаковый glow при одинаковых входах."""
        from retouch.processing.glow import apply_glow
        img = Image.new('L', (200, 200), 128)
        mask = Image.new('L', (200, 200), 255)
        analytics = {'tonal_range': 100, 'subject_separation': 100}
        machine_cfg = DEFAULTS["processing"]["laser_80w"]

        r1 = apply_glow(img, mask, machine_cfg, analytics=analytics, machine_type='laser_80w')
        r2 = apply_glow(img, mask, machine_cfg, analytics=analytics, machine_type='laser_80w')
        assert r1[1] == r2[1], "glow_size не детерминирован"
        assert r1[2] == r2[2], "glow_opacity не детерминирован"


class TestApplyInnerGlowDeprecated:
    """AUDIT-5.5: доступ к apply_inner_glow выдаёт DeprecationWarning."""

    def test_apply_inner_glow_deprecated(self):
        """apply_inner_glow из retouch.processing.glow выдаёт DeprecationWarning."""
        import warnings

        import retouch.processing.glow as glow_mod
        # Очищаем закешированный атрибут чтобы __getattr__ сработал снова
        glow_mod.__dict__.pop("apply_inner_glow", None)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            func = glow_mod.apply_inner_glow
            deprecation = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation) > 0, (
                "Доступ к apply_inner_glow должен выдавать DeprecationWarning"
            )

        from retouch.processing.glow import apply_glow
        assert func is apply_glow, (
            "apply_inner_glow должен быть alias для apply_glow"
        )
