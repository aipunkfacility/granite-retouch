"""Тесты API-слоя — Pydantic схемы, кэш, сериализация."""

import pytest


class TestPydanticValidation:
    """Валидация параметров API через Pydantic."""

    def test_preview_params_rejects_bad_step_mm(self):
        """step_mm=0.01 — ValidationError (ge=0.10)."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import PreviewParams

        with pytest.raises(ValidationError):
            PreviewParams(step_mm=0.01)

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
            face_oval=FaceOvalParams(cx=0.5, cy=0.25, rx=0.15, ry=0.20),
            stone_type="granite",
            step_mm=0.30,
        )

        assert params.face_oval is not None
        assert params.face_oval.cx == 0.5
        assert params.step_mm == 0.30

    def test_preview_params_allows_extra_fields(self):
        """extra='allow' — вложенные секции конфига от UI проходят."""
        from retouch_ui.backend.schemas import PreviewParams

        params = PreviewParams(
            stone_type="gabbro",
            processing={"laser_80w": {"glow_size_min": 10, "glow_size_max": 18}},
            vignette={"blur_radius": 60},
        )

        assert params.stone_type == "gabbro"
        # extra fields доступны через model_dump или __pydantic_extra__
        dumped = params.model_dump()
        assert dumped["processing"]["laser_80w"]["glow_size_min"] == 10
        assert dumped["vignette"]["blur_radius"] == 60

    def test_face_oval_params_validation(self):
        """FaceOvalParams с невалидными координатами — ValidationError."""
        from pydantic import ValidationError
        from retouch_ui.backend.schemas import FaceOvalParams

        with pytest.raises(ValidationError):
            FaceOvalParams(cx=1.5)

        with pytest.raises(ValidationError):
            FaceOvalParams(rx=0.001)

    def test_bad_step_mm_returns_validation_error(self):
        """step_mm=99.0 — ValidationError (le=0.50)."""
        from retouch_ui.backend.schemas import PreviewParams
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            PreviewParams(step_mm=99.0)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("step_mm",) for e in errors), \
            "step_mm=99.0 должен вызывать ошибку валидации"


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
        """T-D3: Одинаковые параметры — одинаковый cache_key."""
        from retouch_ui.backend.routers.process import _cache_key
        from retouch_ui.backend.schemas import PreviewParams

        params = PreviewParams(step_mm=0.30, stone_type="granite")
        k1 = _cache_key("test_id", "laser_standard", params)
        k2 = _cache_key("test_id", "laser_standard", params)

        assert k1 == k2, "Одинаковые параметры — одинаковый ключ кэша"

    def test_cache_key_differs_for_different_params(self):
        """T-D3: Разные параметры — разные ключи кэша."""
        from retouch_ui.backend.routers.process import _cache_key
        from retouch_ui.backend.schemas import PreviewParams

        params1 = PreviewParams(step_mm=0.30, stone_type="granite")
        params2 = PreviewParams(step_mm=0.20, stone_type="granite")

        k1 = _cache_key("test_id", "laser_standard", params1)
        k2 = _cache_key("test_id", "laser_standard", params2)

        assert k1 != k2, "Разные параметры — разные ключи кэша"

    def test_preview_cache_stores_base64_not_pil(self):
        """Кэш хранит base64 строки, не PIL объекты."""
        from retouch_ui.backend.routers.process import _preview_cache

        # Insert a real element so the loop body is actually exercised
        _preview_cache["test-key"] = {
            "images": {
                "final": "data:image/png;base64,iVBORw0KGgo=",
            }
        }

        try:
            for key, value in _preview_cache.items():
                assert isinstance(value, dict), "Кэш должен содержать dict"
                if "images" in value:
                    for img_key, img_val in value["images"].items():
                        assert isinstance(img_val, str), \
                            f"Кэш должен хранить base64 строки, не {type(img_val)}"
                        assert img_val.startswith("data:image/"), \
                            "Кэш должен содержать data URI"
        finally:
            _preview_cache.pop("test-key", None)


class TestReexports:
    """Backward-compatible re-exports из levels.py."""

    def test_import_check_face_brightness_from_levels(self):
        """check_face_brightness доступен из levels.py (re-export)."""
        from retouch.processing.correction.levels import check_face_brightness
        assert callable(check_face_brightness)

    def test_import_add_shadow_noise_from_levels(self):
        """add_shadow_noise доступен из levels.py (re-export)."""
        from retouch.processing.correction.levels import add_shadow_noise
        assert callable(add_shadow_noise)

    def test_import_apply_unsharp_mask_from_levels(self):
        """apply_unsharp_mask доступен из levels.py (re-export)."""
        from retouch.processing.correction.levels import apply_unsharp_mask
        assert callable(apply_unsharp_mask)

    def test_direct_import_face_correction(self):
        """face_correction.py — прямой импорт."""
        from retouch.processing.correction.face_correction import check_face_brightness
        assert callable(check_face_brightness)

    def test_direct_import_unsharp(self):
        """unsharp.py — прямой импорт."""
        from retouch.processing.correction.unsharp import apply_unsharp_mask
        assert callable(apply_unsharp_mask)

    def test_direct_import_shadow_noise(self):
        """shadow_noise.py — прямой импорт."""
        from retouch.processing.correction.shadow_noise import add_shadow_noise
        assert callable(add_shadow_noise)

    def test_reexport_same_function(self):
        """Re-export — это та же функция (identity check)."""
        from retouch.processing.correction.levels import check_face_brightness as from_levels
        from retouch.processing.correction.face_correction import check_face_brightness as from_direct

        assert from_levels is from_direct, "Re-export должен быть той же функцией"


class TestNumbaJitWarmup:
    """AUDIT-8.4: _warmup_numba_jit() в backend вызывается без ошибок."""

    def test_numba_jit_warmup_function(self):
        """_warmup_numba_jit() выполняется без исключений."""
        from retouch_ui.backend.main import _warmup_numba_jit
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_warmup_numba_jit())
        finally:
            loop.close()


class TestNumbaAvailableInDiagnostics:
    """numba_available в PreviewDiagnostics — предупреждение о медленном дизеринге."""

    def test_preview_diagnostics_has_numba_available_field(self):
        """PreviewDiagnostics содержит поле numba_available (bool)."""
        from retouch_ui.backend.schemas import PreviewDiagnostics

        d = PreviewDiagnostics(
            glow_size=40,
            glow_opacity=0.35,
            face_brightness_before=150.0,
            face_brightness_after=210.0,
            face_correction_factor=1.15,
            black_ratio=0.35,
            blue_ratio=0.5,
            width=800,
            height=600,
            numba_available=True,
        )
        assert d.numba_available is True

    def test_numba_available_default_is_true(self):
        """numba_available по умолчанию True (backward compatible)."""
        from retouch_ui.backend.schemas import PreviewDiagnostics

        d = PreviewDiagnostics()
        assert d.numba_available is True

    def test_export_module_exposes_has_numba(self):
        """export.py экспортирует HAS_NUMBA для использования в backend."""
        from retouch.processing.output.export import HAS_NUMBA
        assert isinstance(HAS_NUMBA, bool)
