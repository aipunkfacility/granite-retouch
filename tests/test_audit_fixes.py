"""Дополнительные тесты для аудита — D.4, D.6, F.1, C.3."""

import json
import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS


class TestC3FaceMaskInCheckFaceBrightness:
    """C.3: face_mask используется для замера яркости в check_face_brightness."""

    def test_face_mask_img_overrides_face_region_top(self):
        """При передаче face_mask_img — замер по ней, не по face_region_top."""
        from retouch.processing.face_correction import check_face_brightness

        # Изображение 200x300: верхняя часть тёмная, нижняя — яркая
        arr = np.full((300, 200), 200, dtype=np.uint8)  # яркое
        arr[:100, :] = 50  # верхняя треть тёмная

        img = Image.fromarray(arr, "L")
        subject_mask = Image.new("L", (200, 300), 255)

        # Маска лица — нижняя часть (где яркие пиксели)
        face_mask_arr = np.zeros((300, 200), dtype=np.uint8)
        face_mask_arr[200:, :] = 255
        face_mask_img = Image.fromarray(face_mask_arr, "L")

        # С face_mask_img → замер по маске (нижняя часть, яркость ~200)
        _, before_with_mask, _, _ = check_face_brightness(
            img, [180, 220], subject_mask,
            face_mask_img=face_mask_img,
        )

        # Без face_mask_img → legacy face_region_top=0.45 → верхняя часть (яркость ~50-200)
        _, before_legacy, _, _ = check_face_brightness(
            img, [180, 220], subject_mask,
            face_region_top=0.45,
        )

        # Замеры должны отличаться — face_mask берёт нижнюю часть (ярче)
        assert before_with_mask > before_legacy, \
            f"face_mask должен замерять по маске ({before_with_mask:.1f}), " \
            f"не по face_region_top ({before_legacy:.1f})"

    def test_face_mask_none_uses_legacy(self):
        """face_mask_img=None → legacy поведение (face_region_top)."""
        from retouch.processing.face_correction import check_face_brightness

        arr = np.full((200, 200), 150, dtype=np.uint8)
        img = Image.fromarray(arr, "L")
        subject_mask = Image.new("L", (200, 200), 255)

        # Оба вызова без face_mask — должны дать одинаковый результат
        _, b1, _, _ = check_face_brightness(img, [180, 220], subject_mask, face_region_top=0.45)
        _, b2, _, _ = check_face_brightness(img, [180, 220], subject_mask, face_region_top=0.45, face_mask_img=None)

        assert b1 == b2


class TestD4PydanticValidation:
    """D.4: Pydantic валидация параметров API."""

    def test_preview_params_rejects_bad_brightness(self):
        """brightness=999 → ValidationError."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import PreviewParams

        with pytest.raises(ValidationError):
            PreviewParams(brightness=999)

    def test_preview_params_rejects_bad_glow_size(self):
        """glow_size=0 → ValidationError (ge=5)."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import PreviewParams

        with pytest.raises(ValidationError):
            PreviewParams(glow_size=0)

    def test_preview_params_rejects_bad_stone_type(self):
        """stone_type='obsidian' → ValidationError."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import PreviewParams

        with pytest.raises(ValidationError):
            PreviewParams(stone_type="obsidian")

    def test_preview_params_accepts_valid(self):
        """Валидные параметры проходят."""
        from retouch_ui.backend.schemas import PreviewParams, FaceOvalParams

        params = PreviewParams(
            brightness=1.2,
            glow_size=50,
            glow_opacity=40,
            face_oval=FaceOvalParams(cx=0.5, cy=0.25, rx=0.15, ry=0.20),
            stone_type="granite",
        )

        assert params.brightness == 1.2
        assert params.face_oval is not None
        assert params.face_oval.cx == 0.5

    def test_face_oval_params_validation(self):
        """FaceOvalParams с невалидными координатами → ValidationError."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import FaceOvalParams

        # cx > 1.0 → невалидно
        with pytest.raises(ValidationError):
            FaceOvalParams(cx=1.5)

        # rx < 0.01 → невалидно
        with pytest.raises(ValidationError):
            FaceOvalParams(rx=0.001)


class TestD6StableSerialize:
    """D.6: Стабильная сериализация для кэша."""

    def test_stable_serialize_float_equality(self):
        """_stable_serialize({a: 1.0}) == _stable_serialize({a: 1.0000})."""
        from retouch_ui.backend.routers.process import _stable_serialize

        h1 = _stable_serialize({"a": 1.0})
        h2 = _stable_serialize({"a": 1.0000})
        h3 = _stable_serialize({"a": 1.0001})

        assert h1 == h2, "1.0 и 1.0000 должны давать один хэш"
        assert h1 != h3, "1.0 и 1.0001 должны давать разные хэши"

    def test_stable_serialize_key_order(self):
        """Порядок ключей не влияет на хэш."""
        from retouch_ui.backend.routers.process import _stable_serialize

        h1 = _stable_serialize({"a": 1, "b": 2})
        h2 = _stable_serialize({"b": 2, "a": 1})

        assert h1 == h2, "Порядок ключей не должен влиять на хэш"

    def test_cache_key_deterministic(self):
        """Одинаковые параметры → одинаковый cache_key."""
        from retouch_ui.backend.routers.process import _cache_key
        from retouch_ui.backend.schemas import PreviewParams

        params = PreviewParams(brightness=1.1, glow_size=50)
        k1 = _cache_key("abc123", "laser_standard", params)
        k2 = _cache_key("abc123", "laser_standard", params)

        assert k1 == k2, "Одинаковые параметры → одинаковый ключ кэша"


class TestF1Reexports:
    """F.1: Backward-compatible re-exports из levels.py."""

    def test_import_check_face_brightness_from_levels(self):
        """check_face_brightness доступен из levels.py (re-export)."""
        from retouch.processing.levels import check_face_brightness
        assert callable(check_face_brightness)

    def test_import_add_shadow_noise_from_levels(self):
        """add_shadow_noise доступен из levels.py (re-export)."""
        from retouch.processing.levels import add_shadow_noise
        assert callable(add_shadow_noise)

    def test_import_apply_unsharp_mask_from_levels(self):
        """apply_unsharp_mask доступен из levels.py (re-export)."""
        from retouch.processing.levels import apply_unsharp_mask
        assert callable(apply_unsharp_mask)

    def test_direct_import_face_correction(self):
        """face_correction.py — прямой импорт."""
        from retouch.processing.face_correction import check_face_brightness
        assert callable(check_face_brightness)

    def test_direct_import_unsharp(self):
        """unsharp.py — прямой импорт."""
        from retouch.processing.unsharp import apply_unsharp_mask
        assert callable(apply_unsharp_mask)

    def test_direct_import_shadow_noise(self):
        """shadow_noise.py — прямой импорт."""
        from retouch.processing.shadow_noise import add_shadow_noise
        assert callable(add_shadow_noise)

    def test_reexport_same_function(self):
        """Re-export — это та же функция (identity check)."""
        from retouch.processing.levels import check_face_brightness as from_levels
        from retouch.processing.face_correction import check_face_brightness as from_direct

        assert from_levels is from_direct, "Re-export должен быть той же функцией"
