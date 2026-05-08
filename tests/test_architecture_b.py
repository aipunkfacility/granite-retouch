"""Тесты этапа B — архитектура ядра.

B.1: PipelineContext — внутренняя упаковка
B.2: Миграция конфигурации (трёхуровневая)
B.3: Analytics dataclass
"""

import copy
import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS, resolve_config, STONE_PROFILES


class TestB1PipelineContext:
    """B.1: PipelineContext — внутренняя упаковка."""

    def test_context_creation(self):
        """PipelineContext создаётся с параметрами."""
        from retouch.processing.pipeline import PipelineContext

        img = Image.new("L", (100, 100), 128)
        ctx = PipelineContext(img_gray=img, machine_type="laser_standard")

        assert ctx.img_gray is not None
        assert ctx.machine_type == "laser_standard"
        assert ctx.face_mask is None
        assert ctx.face_oval is None

    def test_context_with_all_fields(self):
        """PipelineContext принимает все поля."""
        from retouch.processing.pipeline import PipelineContext

        img = Image.new("L", (100, 100), 128)
        mask = Image.new("L", (100, 100), 255)
        ctx = PipelineContext(
            img_gray=img,
            subject_mask=mask,
            machine_type="impact",
            stone_type="gabbro",
            step_mm=0.250,
        )

        assert ctx.stone_type == "gabbro"
        assert ctx.step_mm == 0.250


class TestB2ConfigMigration:
    """B.2: Трёхуровневая система параметров."""

    def test_ui_overrides_order(self):
        """UI-параметры перекрывают order.json."""
        config = copy.deepcopy(DEFAULTS)

        result = resolve_config(
            processing_params={"processing": {"blue_threshold": 50}},
            order_params={"processing": {"blue_threshold": 40}},
            config_params=config,
        )

        assert result["processing"]["blue_threshold"] == 50

    def test_order_overrides_config(self):
        """order.json перекрывает config.yaml."""
        config = copy.deepcopy(DEFAULTS)

        result = resolve_config(
            order_params={"processing": {"blue_threshold": 40}},
            config_params=config,
        )

        assert result["processing"]["blue_threshold"] == 40

    def test_config_as_fallback(self):
        """config.yaml — базовый уровень (низший приоритет)."""
        result = resolve_config(config_params=DEFAULTS)

        assert result["processing"]["blue_threshold"] == 30

    def test_stone_profiles_exist(self):
        """STONE_PROFILES содержит типы камней."""
        assert "granite" in STONE_PROFILES
        assert "gabbro" in STONE_PROFILES
        assert "marble" in STONE_PROFILES
        assert "basalt" in STONE_PROFILES

    def test_new_config_fields_exist(self):
        """Новые поля в DEFAULTS."""
        assert "machine" in DEFAULTS
        assert "stone" in DEFAULTS
        assert DEFAULTS["machine"]["step_mm"] == 0.300
        assert DEFAULTS["stone"]["type"] == "granite"

    def test_glow_style_in_defaults(self):
        """glow_style есть в DEFAULTS для каждого станка."""
        for machine in ("laser_standard", "laser_80w", "impact"):
            mc = DEFAULTS["processing"][machine]
            assert "glow_style" in mc, f"{machine} missing glow_style"
            assert mc["glow_style"] in ("inner", "outer")

    def test_shadow_floor_in_impact(self):
        """shadow_floor есть для impact в DEFAULTS."""
        impact = DEFAULTS["processing"]["impact"]
        assert "shadow_floor" in impact
        assert impact["shadow_floor"] > 0

    def test_legacy_step_order_in_defaults(self):
        """legacy_step_order есть в DEFAULTS."""
        assert "legacy_step_order" in DEFAULTS["processing"]
        assert DEFAULTS["processing"]["legacy_step_order"] is False


class TestB3AnalyticsDataclass:
    """B.3: ImageAnalytics dataclass."""

    def test_from_dict_roundtrip(self):
        """from_dict(to_dict()) == исходный dict (круговой обход)."""
        from retouch.processing.analysis import ImageAnalytics

        original = {
            'median_brightness': 130.0,
            'mean_brightness': 125.0,
            'p10_brightness': 45.0,
            'p25_brightness': 80.0,
            'p75_brightness': 180.0,
            'p90_brightness': 210.0,
            'tonal_range': 165.0,
            'highlight_clipping_pct': 0.5,
            'shadow_clipping_pct': 2.0,
            'bg_median_brightness': 10.0,
            'bg_mean_brightness': 12.0,
            'subject_separation': 120.0,
            'input_class': 'medium',
        }

        analytics = ImageAnalytics.from_dict(original)
        result = analytics.to_dict()

        assert result == original, "Круговой обход from_dict→to_dict должен сохранять данные"

    def test_from_dict_ignores_unknown_keys(self):
        """from_dict игнорирует неизвестные ключи."""
        from retouch.processing.analysis import ImageAnalytics

        data = {
            'median_brightness': 130.0,
            'unknown_key': 'should_be_ignored',
        }

        analytics = ImageAnalytics.from_dict(data)
        assert analytics.median_brightness == 130.0
        assert not hasattr(analytics, 'unknown_key') or 'unknown_key' not in analytics.__dataclass_fields__

    def test_default_values(self):
        """ImageAnalytics имеет дефолтные значения."""
        from retouch.processing.analysis import ImageAnalytics

        analytics = ImageAnalytics()
        assert analytics.median_brightness == 0.0
        assert analytics.input_class == 'dark'

    def test_analyze_input_compatible_with_dataclass(self):
        """Результат analyze_input() совместим с ImageAnalytics.from_dict()."""
        from retouch.processing.analysis import analyze_input, ImageAnalytics

        # Создаём тестовое изображение
        arr = np.full((200, 200), 128, dtype=np.uint8)
        mask = np.full((200, 200), 255, dtype=np.uint8)
        img = Image.fromarray(arr, "L")

        result = analyze_input(img, mask)
        analytics = ImageAnalytics.from_dict(result)

        assert analytics.median_brightness > 0
        assert analytics.input_class in ('dark', 'medium', 'bright', 'overbright')
