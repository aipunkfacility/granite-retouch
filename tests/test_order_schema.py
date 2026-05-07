"""Валидация order.json по schema.json.

Спецификация Фазы 7:
  - order.json соответствует schema.json
  - обязательные поля: order_id, machine_type, source_photo, status
  - crm_company_id формат: CMP-NNNN
  - order_id формат: ORD-YYYY-NNN
  - невалидные order.json отбрасываются с понятной ошибкой
"""

import json
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Пути к реальным файлам проекта
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "orders" / "schema.json"
TEMPLATE_ORDER_PATH = PROJECT_ROOT / "orders" / "template" / "order.json"
TEST_ORDER_PATH = PROJECT_ROOT / "orders" / "active" / "TEST_ORDER" / "order.json"

# Попытка импортировать jsonschema — без него часть тестов skip
try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

requires_jsonschema = pytest.mark.skipif(
    not HAS_JSONSCHEMA,
    reason="jsonschema not installed (pip install jsonschema)",
)


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


def _load_schema():
    """Загрузить schema.json проекта."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _valid_order(**overrides):
    """Минимальный валидный order.json."""
    order = {
        "order_id": "ORD-2026-001",
        "machine_type": "laser_standard",
        "source_photo": "source.jpg",
        "status": "new",
    }
    order.update(overrides)
    return order


def _write_order(order: dict, directory: Path) -> Path:
    """Записать order.json во временную директорию и вернуть путь."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "order.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False)
    return path


def _validate(order: dict) -> list[str]:
    """Валидировать order против schema, вернуть список ошибок."""
    schema = _load_schema()
    errors = []
    validator = jsonschema.Draft7Validator(schema)
    for err in sorted(validator.iter_errors(order), key=lambda e: list(e.path)):
        errors.append(f"{'.'.join(str(p) for p in err.path)}: {err.message}")
    return errors


# ---------------------------------------------------------------------------
# Тесты: schema.json целостность
# ---------------------------------------------------------------------------


class TestSchemaIntegrity:
    """schema.json существует и корректен."""

    def test_schema_file_exists(self):
        """schema.json присутствует в проекте."""
        assert SCHEMA_PATH.is_file(), f"schema.json not found at {SCHEMA_PATH}"

    def test_schema_is_valid_json(self):
        """schema.json — парсибельный JSON."""
        data = _load_schema()
        assert isinstance(data, dict)

    def test_schema_has_required_fields(self):
        """В schema указаны обязательные поля."""
        schema = _load_schema()
        required = set(schema.get("required", []))
        assert {"order_id", "machine_type", "source_photo", "status"}.issubset(
            required
        ), f"Missing required fields in schema: {required}"

    def test_schema_crm_pattern(self):
        """crm_company_id имеет паттерн CMP-NNNN."""
        schema = _load_schema()
        crm_props = schema["properties"]["crm_company_id"]
        assert "pattern" in crm_props
        assert "CMP-" in crm_props["pattern"]

    def test_schema_machine_enum(self):
        """machine_type ограничен laser_standard/laser_80w/impact."""
        schema = _load_schema()
        enum = schema["properties"]["machine_type"]["enum"]
        assert set(enum) == {"laser_standard", "laser_80w", "impact"}


# ---------------------------------------------------------------------------
# Тесты: валидные order.json
# ---------------------------------------------------------------------------


@requires_jsonschema
class TestValidOrders:
    """Валидные заказы проходят проверку."""

    def test_minimal_valid_order(self):
        """Минимальный заказ с 4 обязательными полями — валиден."""
        errors = _validate(_valid_order())
        assert errors == [], f"Unexpected errors: {errors}"

    def test_full_valid_order(self):
        """Полный заказ со всеми опциональными полями — валиден."""
        order = _valid_order(
            crm_company_id="CMP-0042",
            client={"name": "Иванов И.И.", "contact": "+7-999-123-45-67"},
            machine_model="Mirtels L60120",
            status="analyzing",
            analyzer_output={
                "clothing_style": "civilian",
                "headgear": "none",
                "face_quality": "high",
                "defects": ["scratches"],
            },
            final_prompt="Portrait of...",
            generated_image="output.png",
            postprocessing={"gimp_processed": "output_gimp.png"},
            final_file="final.tif",
            created_at="2026-05-04T12:00:00+07:00",
            notes="Срочный заказ",
        )
        errors = _validate(order)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_crm_company_id_valid(self):
        """crm_company_id в формате CMP-NNNN — валиден."""
        for crm_id in ["CMP-0001", "CMP-1234", "CMP-9999"]:
            errors = _validate(_valid_order(crm_company_id=crm_id))
            assert errors == [], f"{crm_id} should be valid"

    def test_order_id_formats(self):
        """order_id в формате ORD-YYYY-NNN — валиден."""
        for oid in ["ORD-2026-001", "ORD-2025-999", "ORD-1999-000"]:
            errors = _validate(_valid_order(order_id=oid))
            assert errors == [], f"{oid} should be valid"

    def test_all_status_values(self):
        """Все допустимые значения status — валидны."""
        for status in ["new", "analyzing", "prompting", "generating", "postprocessing", "done"]:
            errors = _validate(_valid_order(status=status))
            assert errors == [], f"status={status} should be valid"


# ---------------------------------------------------------------------------
# Тесты: невалидные order.json
# ---------------------------------------------------------------------------


@requires_jsonschema
class TestInvalidOrders:
    """Невалидные заказы отбрасываются."""

    def test_missing_order_id(self):
        """Нет order_id — ошибка."""
        order = _valid_order()
        del order["order_id"]
        errors = _validate(order)
        assert any("order_id" in e for e in errors), f"Expected order_id error, got: {errors}"

    def test_missing_machine_type(self):
        """Нет machine_type — ошибка."""
        order = _valid_order()
        del order["machine_type"]
        errors = _validate(order)
        assert any("machine_type" in e for e in errors)

    def test_missing_source_photo(self):
        """Нет source_photo — ошибка."""
        order = _valid_order()
        del order["source_photo"]
        errors = _validate(order)
        assert any("source_photo" in e for e in errors)

    def test_missing_status(self):
        """Нет status — ошибка."""
        order = _valid_order()
        del order["status"]
        errors = _validate(order)
        assert any("status" in e for e in errors)

    def test_invalid_machine_type(self):
        """Несуществующий machine_type — ошибка."""
        errors = _validate(_valid_order(machine_type="plasma"))
        assert any("machine_type" in e for e in errors)

    def test_old_laser_machine_type_is_invalid(self):
        """Старое значение 'laser' больше не допустимо."""
        errors = _validate(_valid_order(machine_type="laser"))
        assert any("machine_type" in e for e in errors)

    def test_invalid_crm_id_format(self):
        """Неправильный формат crm_company_id — ошибка."""
        for bad_id in ["CMP-12", "CMP-12345", "cmp-1234", "ABC-1234", "CMP-ABCD"]:
            errors = _validate(_valid_order(crm_company_id=bad_id))
            assert any("crm_company_id" in e for e in errors), f"{bad_id} should be invalid"

    def test_invalid_order_id_format(self):
        """Неправильный формат order_id — ошибка."""
        for bad_oid in ["TEST_ORDER", "ORD-26-01", "2026-001", "ord-2026-001"]:
            errors = _validate(_valid_order(order_id=bad_oid))
            assert any("order_id" in e for e in errors), f"{bad_oid} should be invalid"

    def test_invalid_status(self):
        """Несуществующий status — ошибка."""
        errors = _validate(_valid_order(status="cancelled"))
        assert any("status" in e for e in errors)

    def test_invalid_clothing_style(self):
        """Несуществующий clothing_style — ошибка."""
        order = _valid_order(analyzer_output={"clothing_style": "spacesuit"})
        errors = _validate(order)
        assert any("clothing_style" in e for e in errors)


# ---------------------------------------------------------------------------
# Тесты: реальные файлы проекта
# ---------------------------------------------------------------------------


@requires_jsonschema
class TestProjectOrderFiles:
    """Реальные order.json проекта проходят валидацию."""

    def test_template_order_structure(self):
        """orders/template/order.json имеет правильную структуру."""
        with open(TEMPLATE_ORDER_PATH, "r", encoding="utf-8") as f:
            order = json.load(f)
        # Шаблон содержит пустые строки как placeholders — они не проходят
        # строгий паттерн-чек (crm_company_id: ""), но обязательные поля на месте
        assert "order_id" in order
        assert "machine_type" in order
        assert order["machine_type"] in ("laser_standard", "laser_80w", "impact")
        assert "source_photo" in order
        assert "status" in order

    def test_template_order_fills_to_valid(self):
        """Шаблон становится валидным после заполнения placeholder-полей."""
        with open(TEMPLATE_ORDER_PATH, "r", encoding="utf-8") as f:
            order = json.load(f)
        # Убираем пустые строки из опциональных полей с паттернами
        order.pop("crm_company_id", None)
        errors = _validate(order)
        assert errors == [], f"Filled template should be valid: {errors}"

    def test_test_order_exists(self):
        """TEST_ORDER/order.json существует."""
        assert TEST_ORDER_PATH.is_file(), f"Test order not found at {TEST_ORDER_PATH}"


# ---------------------------------------------------------------------------
# Тесты: validate_order() из retouch.validation.order
# ---------------------------------------------------------------------------


@requires_jsonschema
class TestValidateOrderFunction:
    """Функция validate_order() из retouch.validation.order."""

    def test_validate_order_valid(self, tmp_path):
        """Валидный заказ — возвращает dict без ошибки."""
        from retouch.validation.order import validate_order, OrderValidationError

        order = _valid_order()
        path = _write_order(order, tmp_path / "ORD-2026-042")
        result = validate_order(path, schema_path=SCHEMA_PATH)
        assert isinstance(result, dict)
        assert result["order_id"] == "ORD-2026-001"

    def test_validate_order_missing_file(self, tmp_path):
        """Несуществующий файл — OrderValidationError."""
        from retouch.validation.order import validate_order, OrderValidationError

        with pytest.raises(OrderValidationError, match="не найден"):
            validate_order(tmp_path / "nonexistent" / "order.json")

    def test_validate_order_invalid_content(self, tmp_path):
        """Невалидный заказ — OrderValidationError."""
        from retouch.validation.order import validate_order, OrderValidationError

        order = {"machine_type": "laser_standard"}  # нет обязательных полей
        path = _write_order(order, tmp_path / "BAD-001")
        with pytest.raises(OrderValidationError, match="не соответствует схеме"):
            validate_order(path, schema_path=SCHEMA_PATH)

    def test_validate_order_auto_schema_detection(self, tmp_path):
        """Авто-детекция schema.json по пути заказа."""
        from retouch.validation.order import validate_order, OrderValidationError

        # Создаём структуру: tmp_path/orders/active/ORD-2026-001/order.json
        # и tmp_path/orders/schema.json
        order_dir = tmp_path / "orders" / "active" / "ORD-2026-001"
        order = _valid_order()
        _write_order(order, order_dir)

        # Копируем schema.json
        schema_dir = tmp_path / "orders"
        schema_dest = schema_dir / "schema.json"
        schema_dest.write_text(SCHEMA_PATH.read_text(encoding="utf-8"), encoding="utf-8")

        order_path = order_dir / "order.json"
        result = validate_order(order_path)  # schema_path=None → auto-detect
        assert isinstance(result, dict)
        assert result["order_id"] == "ORD-2026-001"
