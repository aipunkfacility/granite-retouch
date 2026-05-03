"""Валидация order.json по schema.json."""

import json
from pathlib import Path


class OrderValidationError(Exception):
    """Ошибка валидации заказа."""
    pass


def validate_order(order_path, schema_path=None):
    """Проверить order.json по schema.json.

    Args:
        order_path: путь к order.json
        schema_path: путь к schema.json (default: auto-detect)

    Returns:
        dict: распарсенный order.json

    Raises:
        OrderValidationError: при проблемах с валидацией
    """
    try:
        import jsonschema
        HAS_JSONSCHEMA = True
    except ImportError:
        HAS_JSONSCHEMA = False

    order_path = Path(order_path)
    if not order_path.is_file():
        raise OrderValidationError(f"Файл заказа не найден: {order_path}")

    with open(order_path, "r", encoding="utf-8") as f:
        order = json.load(f)

    if not HAS_JSONSCHEMA:
        print("Warning: jsonschema not installed, skipping schema validation. "
              "Install: uv pip install jsonschema")
        return order

    if schema_path is None:
        # Auto-detect: orders/schema.json relative to order file
        project_root = order_path.parent
        while project_root.parent != project_root:
            candidate = project_root / "orders" / "schema.json"
            if candidate.is_file():
                schema_path = candidate
                break
            project_root = project_root.parent

    if schema_path is None:
        print("Warning: schema.json not found, skipping validation")
        return order

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    try:
        jsonschema.validate(order, schema)
    except jsonschema.ValidationError as e:
        raise OrderValidationError(f"order.json не соответствует схеме: {e.message}")

    print(f"Order validated: {order_path}")
    return order
