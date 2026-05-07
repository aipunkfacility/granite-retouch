#!/usr/bin/env python3
"""granite-retouch — единая точка входа CLI.

Команды:
  python -m retouch process -i ... -o ... -m laser_standard   # Pillow-обработка
  python -m retouch validate -i ai.png                # Валидация изображения
  python -m retouch gimp -i ... -o ... -m impact      # GIMP-обработка (experimental)
  python -m retouch order list                         # Список заказов
  python -m retouch order validate ORD-2026-001        # Валидация заказа
  python -m retouch order create ORD-2026-042          # Создать заказ из шаблона
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from retouch.config import load_config
from retouch.validation.image import ValidationError
from retouch.validation.order import validate_order, OrderValidationError


def cmd_process(args):
    """Pillow-обработка портрета."""
    from retouch.processing.pipeline import process

    config = load_config(args.config)

    if args.no_validate:
        if not os.path.isfile(args.input):
            print(f"Error: входной файл не найден: {args.input}", file=sys.stderr)
            sys.exit(1)
        config_noval = dict(config)
        proc_noval = dict(config.get("processing", {}))
        proc_noval["min_blue_ratio"] = 0.0
        proc_noval["min_resolution"] = 0
        proc_noval["result_min_black_ratio"] = 0.0
        config_noval["processing"] = proc_noval
        config = config_noval

    try:
        process(
            args.input, args.output,
            machine_type=args.machine,
            glow_size_override=args.glow_size,
            glow_opacity_override=args.glow_opacity,
            config=config,
            fmt=getattr(args, 'format', 'bmp'),
        )
    except ValidationError as e:
        print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args):
    """Валидация входного изображения."""
    from retouch.validation.image import validate_image_input, validate_blue_chromakey
    from PIL import Image

    config = load_config(args.config)
    proc = config.get("processing", {})

    try:
        validate_image_input(args.input, config)
        img = Image.open(args.input).convert("RGBA")
        threshold = proc.get("blue_threshold", 30)
        ratio = validate_blue_chromakey(img, threshold=threshold)
        print(f"OK: {args.input} — {ratio:.1%} blue pixels")
    except ValidationError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_gimp(args):
    """GIMP-обработка портрета (experimental / not recommended)."""
    print("⚠ Experimental: results may be incorrect. "
          "Use `retouch process` for production.", file=sys.stderr)

    from retouch.gimp.runner import run_gimp

    config = load_config(args.config)

    if not os.path.isfile(args.input):
        print(f"Error: входной файл не найден: {args.input}", file=sys.stderr)
        sys.exit(1)

    exit_code = run_gimp(args.input, args.output, machine_type=args.machine, config=config)
    if exit_code == 0:
        print("GIMP processing complete.")
    sys.exit(exit_code)


def _find_orders_root():
    """Найти корневую директорию orders/ (проект root)."""
    candidates = [
        Path(__file__).resolve().parent.parent / "orders",  # retouch/../orders
        Path.cwd() / "orders",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def cmd_order_list(args):
    """Показать список активных заказов."""
    orders_root = _find_orders_root()
    if orders_root is None:
        print("Error: orders/ directory not found", file=sys.stderr)
        sys.exit(1)

    active_dir = orders_root / "active"
    if not active_dir.is_dir():
        print("No active orders.")
        return

    orders = sorted(active_dir.iterdir()) if active_dir.exists() else []
    if not orders:
        print("No active orders.")
        return

    print(f"{'Order ID':<18} {'Machine':<9} {'Status':<16} {'CRM':<12} {'Client'}")
    print("-" * 75)

    for order_dir in orders:
        if not order_dir.is_dir():
            continue
        order_file = order_dir / "order.json"
        if not order_file.is_file():
            print(f"{order_dir.name:<18} (no order.json)")
            continue

        try:
            with open(order_file, "r", encoding="utf-8") as f:
                order = json.load(f)
            order_id = order.get("order_id", order_dir.name)
            machine = order.get("machine_type", "?")
            status = order.get("status", "?")
            crm_id = order.get("crm_company_id", "")
            client = order.get("client", {}).get("name", "")
            print(f"{order_id:<18} {machine:<9} {status:<16} {crm_id:<12} {client}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"{order_dir.name:<18} (parse error: {e})")


def cmd_order_validate(args):
    """Валидация order.json по schema.json."""
    orders_root = _find_orders_root()
    if orders_root is None:
        print("Error: orders/ directory not found", file=sys.stderr)
        sys.exit(1)

    # Resolve order directory
    order_dir = orders_root / "active" / args.order_id
    order_file = order_dir / "order.json"

    # Also try as direct path
    if not order_file.is_file():
        alt_path = Path(args.order_id)
        if alt_path.is_file():
            order_file = alt_path
        else:
            print(f"Error: заказ не найден: {args.order_id}", file=sys.stderr)
            sys.exit(1)

    schema_path = orders_root / "schema.json"

    try:
        order = validate_order(str(order_file), schema_path=str(schema_path))
        crm_id = order.get("crm_company_id", "")
        if crm_id:
            print(f"OK: {order_file} (CRM: {crm_id})")
        else:
            print(f"OK: {order_file} (no CRM link)")
    except OrderValidationError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_order_create(args):
    """Создать новый заказ из шаблона."""
    orders_root = _find_orders_root()
    if orders_root is None:
        print("Error: orders/ directory not found", file=sys.stderr)
        sys.exit(1)

    template_file = orders_root / "template" / "order.json"
    if not template_file.is_file():
        print(f"Error: шаблон не найден: {template_file}", file=sys.stderr)
        sys.exit(1)

    order_id = args.order_id
    target_dir = orders_root / "active" / order_id

    if target_dir.exists():
        print(f"Error: заказ уже существует: {target_dir}", file=sys.stderr)
        sys.exit(1)

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "order.json"

    with open(template_file, "r", encoding="utf-8") as f:
        order = json.load(f)

    order["order_id"] = order_id
    order["created_at"] = datetime.now(timezone.utc).isoformat()

    if args.crm:
        order["crm_company_id"] = args.crm
    if args.machine:
        order["machine_type"] = args.machine

    # Create generated/ subdirectory
    (target_dir / "generated").mkdir(exist_ok=True)

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(order, f, indent=2, ensure_ascii=False)

    print(f"Created: {target_file}")
    print(f"  Order ID: {order_id}")
    if args.crm:
        print(f"  CRM link: {args.crm}")
    print(f"  Machine:  {order['machine_type']}")
    print(f"  Status:   {order['status']}")
    print(f"  Next: copy source photo to {target_dir}/source.jpg")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="retouch",
        description="granite-retouch — AI-ретушь портретов для гравировки"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- process ---
    p_process = subparsers.add_parser("process", help="Pillow-обработка портрета")
    p_process.add_argument("--input", "-i", required=True, help="Входной PNG (с хромакеем)")
    p_process.add_argument("--output", "-o", required=True, help="Выходной BMP/PNG")
    p_process.add_argument("--machine", "-m", choices=["laser_standard", "laser_80w", "impact"], default="laser_standard")
    p_process.add_argument("--format", "-f", choices=["bmp", "bmp_1bit", "bmp_8bit", "png"], default="bmp", help="Формат экспорта (по умолчанию: bmp)")
    p_process.add_argument("--glow-size", type=int, help="Переопределить размер Inner Glow (px)")
    p_process.add_argument("--glow-opacity", type=int, help="Переопределить opacity Inner Glow (%%)")
    p_process.add_argument("--config", "-c", help="Путь к config.yaml")
    p_process.add_argument("--no-validate", action="store_true", help="Пропустить валидацию")
    p_process.set_defaults(func=cmd_process)

    # --- validate ---
    p_validate = subparsers.add_parser("validate", help="Валидация входного изображения")
    p_validate.add_argument("--input", "-i", required=True, help="Путь к изображению")
    p_validate.add_argument("--config", "-c", help="Путь к config.yaml")
    p_validate.set_defaults(func=cmd_validate)

    # --- gimp ---
    p_gimp = subparsers.add_parser(
        "gimp",
        help="GIMP-обработка (experimental / не рекомендуется для production)"
    )
    p_gimp.add_argument("--input", "-i", required=True, help="Входной PNG")
    p_gimp.add_argument("--output", "-o", required=True, help="Выходной BMP/PNG")
    p_gimp.add_argument("--machine", "-m", choices=["laser_standard", "laser_80w", "impact"], default="laser_standard")
    p_gimp.add_argument("--config", "-c", help="Путь к config.yaml")
    p_gimp.set_defaults(func=cmd_gimp)

    # --- order ---
    p_order = subparsers.add_parser("order", help="Управление заказами")
    order_sub = p_order.add_subparsers(dest="order_command", required=True)

    # order list
    p_olist = order_sub.add_parser("list", help="Список активных заказов")
    p_olist.set_defaults(func=cmd_order_list)

    # order validate
    p_oval = order_sub.add_parser("validate", help="Валидация order.json")
    p_oval.add_argument("order_id", help="ID заказа (напр. ORD-2026-001) или путь к order.json")
    p_oval.set_defaults(func=cmd_order_validate)

    # order create
    p_ocreate = order_sub.add_parser("create", help="Создать заказ из шаблона")
    p_ocreate.add_argument("order_id", help="ID заказа (напр. ORD-2026-042)")
    p_ocreate.add_argument("--crm", help="ID компании в CRM (напр. CMP-0042)")
    p_ocreate.add_argument("--machine", "-m", choices=["laser_standard", "laser_80w", "impact"], default="laser_standard")
    p_ocreate.set_defaults(func=cmd_order_create)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
