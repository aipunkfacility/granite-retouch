"""REFACTOR-4: прямые импорты должны работать вместо re-exports через levels."""

import importlib
import inspect
import warnings

import pytest


class TestDirectImportsWork:
    """Все функции, реэкспортируемые через levels.py, доступны напрямую."""

    def test_unsharp_importable_directly(self):
        from retouch.processing.unsharp import apply_unsharp_mask
        assert callable(apply_unsharp_mask)

    def test_face_correction_importable_directly(self):
        from retouch.processing.face_correction import check_face_brightness
        assert callable(check_face_brightness)

    def test_shadow_noise_importable_directly(self):
        from retouch.processing.shadow_noise import add_shadow_noise
        assert callable(add_shadow_noise)

    def test_mask_utils_importable_directly(self):
        from retouch.processing.mask_utils import apply_masked
        assert callable(apply_masked)


class TestPipelineDirectImports:
    """pipeline.py импортирует функции напрямую, а не через levels."""

    def test_pipeline_imports_unsharp_directly(self):
        """pipeline не должен импортировать apply_unsharp_mask через levels."""
        import retouch.processing.pipeline as pipeline_mod
        src = inspect.getsource(pipeline_mod)
        lines_with_levels = [l for l in src.split('\n')
                             if 'from retouch.processing.levels import' in l]
        for line in lines_with_levels:
            assert 'apply_unsharp_mask' not in line, (
                f"apply_unsharp_mask всё ещё импортируется через levels: {line.strip()}"
            )
            assert 'check_face_brightness' not in line, (
                f"check_face_brightness всё ещё импортируется через levels: {line.strip()}"
            )
            assert 'add_shadow_noise' not in line, (
                f"add_shadow_noise всё ещё импортируется через levels: {line.strip()}"
            )

    def test_pipeline_imports_face_correction_directly(self):
        """pipeline импортирует check_face_brightness из face_correction."""
        import retouch.processing.pipeline as pipeline_mod
        src = inspect.getsource(pipeline_mod)
        assert 'from retouch.processing.face_correction import check_face_brightness' in src, (
            "pipeline должен импортировать check_face_brightness напрямую из face_correction"
        )


class TestLevelsReExportsDeprecated:
    """Re-exports через levels.py должны выдавать DeprecationWarning."""

    def test_import_check_face_brightness_from_levels_warns(self):
        import warnings
        # Пересоздаём импорт — levels модуль уже загружен, но __getattr__
        # вызывается при каждом доступе к устаревшему имени
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import retouch.processing.levels as levels_mod
            # Обращаемся к устаревшему имени — это вызовет __getattr__
            _ = levels_mod.check_face_brightness
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) > 0, (
                "Импорт check_face_brightness через levels.py должен выдавать DeprecationWarning"
            )

    def test_import_apply_levels_from_levels_no_warning(self):
        """apply_levels — НЕ устаревший, DeprecationWarning не должен выдаваться."""
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import retouch.processing.levels as levels_mod
            _ = levels_mod.apply_levels
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0, (
                "apply_levels не должен вызывать DeprecationWarning"
            )

    def test_init_imports_directly_no_warning(self):
        """retouch.processing.__init__ импортирует напрямую — без DeprecationWarning."""
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import retouch.processing as processing_mod
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0, (
                f"__init__.py не должен вызывать DeprecationWarning. "
                f"Warnings: {[str(x.message) for x in deprecation_warnings]}"
            )
