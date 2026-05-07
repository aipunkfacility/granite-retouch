"""Тесты валидации — image.py и order.py."""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from retouch.validation.image import (
    ValidationError,
    validate_image_input,
    validate_blue_chromakey,
    validate_result_black_ratio,
)
from retouch.validation.order import validate_order, OrderValidationError


# ========================================================================
# Image validation
# ========================================================================

class TestValidateImageInput:
    """Тесты валидации входного изображения."""

    def test_valid_chromakey_png(self, chromakey_png, default_config):
        """Валидный PNG с хромакеем проходит проверку."""
        assert validate_image_input(chromakey_png, default_config) is True

    def test_missing_file(self, default_config):
        """Несуществующий файл → ValidationError."""
        with pytest.raises(ValidationError, match="не найден"):
            validate_image_input("/nonexistent/path/image.png", default_config)

    def test_small_resolution(self, small_chromakey_png, default_config):
        """Маленькое изображение (100x100) → ValidationError."""
        # default_config has min_resolution=512
        with pytest.raises(ValidationError, match="Разрешение"):
            validate_image_input(small_chromakey_png, default_config)

    def test_zero_min_resolution(self, small_chromakey_png, default_config):
        """С min_resolution=0 маленькое изображение проходит."""
        config = {"processing": {"min_resolution": 0}}
        # Нужно пересохранить маленькое изображение
        # small_chromakey_png — уже сохранён как PNG
        assert validate_image_input(small_chromakey_png, config) is True

    def test_non_image_file(self, tmp_path, default_config):
        """Не-изображение → ValidationError."""
        bad_file = tmp_path / "not_image.txt"
        bad_file.write_text("this is not an image")
        with pytest.raises(ValidationError, match="Не удалось открыть"):
            validate_image_input(str(bad_file), default_config)


class TestValidateBlueChromakey:
    """Тесты валидации синего хромакея."""

    def test_valid_chromakey(self, chromakey_img):
        """Изображение с хромакеем проходит проверку."""
        img, _ = chromakey_img
        ratio = validate_blue_chromakey(img, threshold=30)
        assert ratio >= 0.15, f"Доля синих пикселей {ratio:.1%} ниже минимума"

    def test_no_chromakey(self, no_chromakey_img):
        """Изображение без хромакея → ValidationError."""
        with pytest.raises(ValidationError, match="Синий хромакей не обнаружен"):
            validate_blue_chromakey(no_chromakey_img, threshold=30)

    def test_returns_ratio(self, chromakey_img):
        """Возвращает долю синих пикселей."""
        img, _ = chromakey_img
        ratio = validate_blue_chromakey(img, threshold=30, min_blue_ratio=0.0)
        assert 0.0 < ratio < 1.0

    def test_custom_threshold(self, chromakey_img):
        """Высокий threshold уменьшает долю «синих» пикселей."""
        img, _ = chromakey_img
        ratio_low = validate_blue_chromakey(img, threshold=20, min_blue_ratio=0.0)
        ratio_high = validate_blue_chromakey(img, threshold=50, min_blue_ratio=0.0)
        assert ratio_high <= ratio_low, \
            "Высокий threshold должен находить меньше синих пикселей"


class TestValidateResultBlackRatio:
    """Тесты проверки доли чёрного фона в результате."""

    def test_mostly_black_passes(self):
        """Изображение с >25% чёрного проходит."""
        arr = np.zeros((512, 512, 3), dtype=np.uint8)
        # 40% чёрного
        arr[:205, :, :] = 0
        arr[205:, :, :] = [128, 128, 128]
        img = Image.fromarray(arr, "RGB")
        ratio = validate_result_black_ratio(img, min_black_ratio=0.25)
        assert ratio >= 0.25

    def test_too_little_black_fails(self):
        """Изображение с <25% чёрного → ValidationError."""
        arr = np.full((512, 512, 3), 128, dtype=np.uint8)
        # Только 5% чёрного
        arr[:25, :, :] = 0
        img = Image.fromarray(arr, "RGB")
        with pytest.raises(ValidationError, match="Недостаточно чёрного фона"):
            validate_result_black_ratio(img, min_black_ratio=0.25)

    def test_zero_black_fails(self):
        """Полностью белое изображение → ValidationError."""
        arr = np.full((512, 512, 3), 255, dtype=np.uint8)
        img = Image.fromarray(arr, "RGB")
        with pytest.raises(ValidationError):
            validate_result_black_ratio(img, min_black_ratio=0.25)


# ========================================================================
# Order validation
# ========================================================================

class TestValidateOrder:
    """Тесты валидации order.json по schema.json."""

    def test_valid_order(self, valid_order_json, schema_path):
        """Валидный order.json проходит проверку."""
        order = validate_order(valid_order_json, schema_path=str(schema_path))
        assert order["order_id"] == "ORD-2026-042"
        assert order["machine_type"] == "laser_standard"

    def test_order_with_crm(self, order_with_crm, schema_path):
        """Заказ с crm_company_id проходит валидацию."""
        order = validate_order(order_with_crm, schema_path=str(schema_path))
        assert order["crm_company_id"] == "CMP-0042"

    def test_missing_file(self):
        """Несуществующий файл → OrderValidationError."""
        with pytest.raises(OrderValidationError, match="не найден"):
            validate_order("/nonexistent/order.json")

    def test_invalid_order_missing_fields(self, invalid_order_json, schema_path):
        """Заказ без обязательных полей → OrderValidationError."""
        with pytest.raises(OrderValidationError, match="не соответствует схеме"):
            validate_order(invalid_order_json, schema_path=str(schema_path))

    def test_invalid_crm_id_format(self, tmp_path, schema_path):
        """Неверный формат crm_company_id → OrderValidationError."""
        order = {
            "order_id": "ORD-2026-042",
            "crm_company_id": "INVALID",
            "machine_type": "laser_standard",
            "source_photo": "source.jpg",
            "status": "new",
        }
        p = tmp_path / "bad_crm.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(order, f)

        with pytest.raises(OrderValidationError, match="не соответствует схеме"):
            validate_order(str(p), schema_path=str(schema_path))

    def test_invalid_machine_type(self, tmp_path, schema_path):
        """Неверный machine_type → OrderValidationError."""
        order = {
            "order_id": "ORD-2026-042",
            "machine_type": "plasma",
            "source_photo": "source.jpg",
            "status": "new",
        }
        p = tmp_path / "bad_machine.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(order, f)

        with pytest.raises(OrderValidationError, match="не соответствует схеме"):
            validate_order(str(p), schema_path=str(schema_path))

    def test_invalid_order_id_format(self, tmp_path, schema_path):
        """Неверный формат order_id → OrderValidationError."""
        order = {
            "order_id": "BAD-ID",
            "machine_type": "laser_standard",
            "source_photo": "source.jpg",
            "status": "new",
        }
        p = tmp_path / "bad_id.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(order, f)

        with pytest.raises(OrderValidationError, match="не соответствует схеме"):
            validate_order(str(p), schema_path=str(schema_path))

    def test_valid_order_id_formats(self, tmp_path, schema_path):
        """Разные валидные форматы order_id проходят."""
        valid_ids = ["ORD-2026-001", "ORD-2025-999", "ORD-2024-042"]
        for oid in valid_ids:
            order = {
                "order_id": oid,
                "machine_type": "laser_standard",
                "source_photo": "source.jpg",
                "status": "new",
            }
            p = tmp_path / f"order_{oid}.json"
            with open(p, "w", encoding="utf-8") as f:
                json.dump(order, f)
            result = validate_order(str(p), schema_path=str(schema_path))
            assert result["order_id"] == oid
