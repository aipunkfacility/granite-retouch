"""Тесты API-слоя — Pydantic схемы, кэш, сериализация."""

import pytest


class TestPydanticValidation:
    """Валидация параметров API через Pydantic."""

    def test_preview_params_rejects_bad_brightness(self):
        """brightness=999 — ValidationError."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import PreviewParams

        with pytest.raises(ValidationError):
            PreviewParams(brightness=999)

    def test_preview_params_rejects_bad_glow_size(self):
        """glow_size=0 — ValidationError (ge=5)."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import PreviewParams

        with pytest.raises(ValidationError):
            PreviewParams(glow_size=0)

    def test_preview_params_rejects_bad_stone_type(self):
        """stone_type='obsidian' — ValidationError."""
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
        """FaceOvalParams с невалидными координатами — ValidationError."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import FaceOvalParams

        with pytest.raises(ValidationError):
            FaceOvalParams(cx=1.5)

        with pytest.raises(ValidationError):
            FaceOvalParams(rx=0.001)

    def test_brightness_999_returns_422(self):
        """brightness=999 — 422 Validation Error."""
        from retouch_ui.backend.schemas import PreviewParams
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            PreviewParams(brightness=999.0)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("brightness",) for e in errors), \
            "brightness=999 должен вызывать ошибку валидации"


class TestStableSerialize:
    """Стабильная сериализация для кэша."""

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
        """Одинаковые параметры — одинаковый cache_key."""
        from retouch_ui.backend.routers.process import _cache_key
        from retouch_ui.backend.schemas import PreviewParams

        params = PreviewParams(brightness=1.1, glow_size=50)
        k1 = _cache_key("abc123", "laser_standard", params)
        k2 = _cache_key("abc123", "laser_standard", params)

        assert k1 == k2, "Одинаковые параметры — одинаковый ключ кэша"

    def test_preview_cache_stores_base64_not_pil(self):
        """Кэш хранит base64 строки, не PIL объекты."""
        from retouch_ui.backend.routers.process import _preview_cache

        for key, value in _preview_cache.items():
            assert isinstance(value, dict), "Кэш должен содержать dict"
            if "images" in value:
                for img_key, img_val in value["images"].items():
                    assert isinstance(img_val, str), \
                        f"Кэш должен хранить base64 строки, не {type(img_val)}"
                    assert img_val.startswith("data:image/"), \
                        "Кэш должен содержать data URI"


class TestReexports:
    """Backward-compatible re-exports из levels.py."""

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
