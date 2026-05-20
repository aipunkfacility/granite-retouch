#!/usr/bin/env python3
"""granite-retouch — единая точка входа CLI.

Команды:
  python -m retouch process -i ... -o ... --preset stanzone-laser-1bit  # Pillow-обработка с пресетом
  python -m retouch process -i ... -o ... -m laser_80w --material gabbro  # С указанием материала
  python -m retouch validate -i ai.png                # Валидация изображения
  python -m retouch gimp -i ... -o ... -m impact      # GIMP-обработка (experimental)
  python -m retouch order list                         # Список заказов
  python -m retouch order validate ORD-2026-001        # Валидация заказа
  python -m retouch order create ORD-2026-042          # Создать заказ из шаблона
  python -m retouch --list-presets                     # Список доступных пресетов
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from retouch.config import load_config, find_config_path
from retouch.presets_catalog import PRESET_CATALOG
from retouch.validation.image import ValidationError
from retouch.validation.order import validate_order, OrderValidationError


def _load_preset_config(preset_name: str):
    """Загрузить конфиг из пресета по имени."""
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML required for --preset. Install: uv pip install PyYAML", file=sys.stderr)
        sys.exit(1)

    config_path = find_config_path()
    if config_path:
        presets_dir = config_path.parent / "presets"
    else:
        presets_dir = Path.cwd() / "presets"

    preset_file = presets_dir / f"{preset_name}.yaml"
    if not preset_file.is_file():
        print(f"Error: пресет '{preset_name}' не найден: {preset_file}", file=sys.stderr)
        sys.exit(1)

    with open(preset_file, "r", encoding="utf-8") as f:
        preset_config = yaml.safe_load(f) or {}

    return preset_config


def cmd_list_presets(args):
    """Показать список доступных пресетов."""
    for name, meta in PRESET_CATALOG.items():
        category_label = "Технология" if meta["category"] == "technology" else "Станок"
        machine_type = meta["machine_type"]
        line = f"{category_label}: {meta['label']} \u2192 {name} [{machine_type}]"
        if meta.get("alert"):
            line += f" \u26a0 {meta['alert']}"
        print(line)


def cmd_process(args):
    """Pillow-обработка портрета."""
    from retouch.processing.core.pipeline import process
    from retouch.config import deep_merge, apply_material_overrides, validate_machine_material

    # D.7: Проверка перезаписи выходного файла
    if os.path.isfile(args.output) and not args.overwrite:
        print(f"Error: выходной файл уже существует: {args.output}\n"
              f"Используйте --overwrite для перезаписи.", file=sys.stderr)
        sys.exit(1)

    # Определить material (из --material или --stone)
    material = getattr(args, "material", None)
    stone_arg = getattr(args, "stone", None)
    if stone_arg and not material:
        import warnings
        warnings.warn("--stone is deprecated, use --material instead", DeprecationWarning, stacklevel=2)
        material = stone_arg

    # Загрузить базовый конфиг
    config = load_config(args.config)

    # Если указан --preset — наложить пресет поверх конфига
    if args.preset:
        preset_config = _load_preset_config(args.preset)
        config = deep_merge(config, preset_config)
        # Определить machine_type из пресета
        for mt in ("laser_standard", "laser_80w", "impact"):
            if mt in preset_config.get("processing", {}):
                config["machine_type"] = mt
                break

    # Если указан -m — переопределить machine_type
    if args.machine:
        config["machine_type"] = args.machine

    # Если указан материал — применить overrides
    if material:
        config["stone"]["material"] = material
        config["stone"]["type"] = material  # backward compat
        machine_type = config.get("machine_type", "laser_standard")
        config, changes = apply_material_overrides(config, material)

        # Валидация совместимости станок+материал
        warnings_list = validate_machine_material(machine_type, material)
        for w in warnings_list:
            if w.startswith("ERROR:"):
                print(f"\u041e\u0428\u0418\u0411\u041a\u0410: {w[7:]}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"\u041f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u0435: {w[9:]}", file=sys.stderr)

        # Показать автокоррекции
        if changes:
            for c in changes:
                if "reason" in c:
                    print(f"  {c['param']}: {c['old']} \u2192 {c['new']} ({c['reason']})", file=sys.stderr)
                else:
                    print(f"  {c['param']}: {c['old']} \u2192 {c['new']}", file=sys.stderr)

    # Определить machine_type для pipeline
    machine_type = config.get("machine_type", args.machine or "laser_standard")

    try:
        process(
            args.input, args.output,
            machine_type=machine_type,
            glow_size_override=args.glow_size,
            glow_opacity_override=args.glow_opacity,
            config=config,
            fmt=getattr(args, 'format', 'bmp'),
            overwrite=args.overwrite,
            no_validate=args.no_validate,
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
    print("[WARN] Experimental: results may be incorrect. "
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


def cmd_debug_report(args):
    """Попиксельный анализ результата пайплайна."""
    from retouch.debug.pixel_report import generate_report

    json_path = args.json
    txt_path = args.txt
    heatmap_path = args.heatmap

    if args.output_dir:
        od = args.output_dir
        os.makedirs(od, exist_ok=True)
        json_path = json_path or os.path.join(od, "pixel-report.json")
        txt_path = txt_path or os.path.join(od, "pixel-report.txt")
        heatmap_path = heatmap_path or os.path.join(od, "heatmap.png")

    generate_report(
        source_path=args.input,
        output_path=args.output,
        machine_type=args.machine,
        face_mask_path=args.face_mask,
        subject_mask_path=args.subject_mask,
        json_path=json_path,
        heatmap_path=heatmap_path,
        txt_path=txt_path,
    )


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


def _warmup_numba_if_needed(args):
    """AUDIT-8.4: Прогрев Numba JIT перед обработкой, если нужен дизеринг."""
    if args.command != "process":
        return
    machine = getattr(args, "machine", "laser_standard")
    if machine in ("laser_80w", "impact"):
        try:
            from retouch.processing.output.export import _error_diffusion_dither
            from PIL import Image
            tiny = Image.new("L", (8, 8), 128)
            _error_diffusion_dither(tiny, [(1, 0, 7/48), (2, 0, 5/48)])
        except Exception:
            pass  # Non-critical


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="retouch",
        description="granite-retouch — AI-ретушь портретов для гравировки"
    )
    parser.add_argument("--list-presets", action="store_true",
                        help="Показать список доступных пресетов")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- process ---
    p_process = subparsers.add_parser("process", help="Pillow-обработка портрета")
    p_process.add_argument("--input", "-i", required=True, help="Входной PNG (с хромакеем)")
    p_process.add_argument("--output", "-o", required=True, help="Выходной BMP/PNG")
    p_process.add_argument("--machine", "-m", choices=["laser_standard", "laser_80w", "impact"], default=None)
    p_process.add_argument("--preset", help="Имя пресета (напр. stanzone-laser-1bit)")
    p_process.add_argument("--material", choices=["granite", "marble", "gabbro", "basalt", "acrylic"],
                           help="Тип материала (камень/акрил)")
    p_process.add_argument("--stone", choices=["granite", "marble", "gabbro", "basalt", "acrylic"],
                           help="Deprecated: используйте --material")
    p_process.add_argument("--format", "-f", choices=["bmp", "bmp_1bit", "bmp_8bit", "png"], default="bmp", help="Формат экспорта (по умолчанию: bmp)")
    p_process.add_argument("--glow-size", type=int, help="Переопределить размер Inner Glow (px)")
    p_process.add_argument("--glow-opacity", type=int, help="Переопределить opacity Inner Glow (%%)")
    p_process.add_argument("--config", "-c", help="Путь к config.yaml")
    p_process.add_argument("--no-validate", action="store_true", help="Пропустить валидацию")
    p_process.add_argument("--overwrite", action="store_true", help="D.7: Перезаписать выходной файл без подтверждения")
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

    # --- debug ---
    p_debug = subparsers.add_parser("debug", help="Диагностика и анализ")
    debug_sub = p_debug.add_subparsers(dest="debug_command", required=True)

    # debug report
    p_dreport = debug_sub.add_parser("report", help="Попиксельный анализ результата пайплайна")
    p_dreport.add_argument("--input", "-i", required=True, help="Исходное изображение (source)")
    p_dreport.add_argument("--output", "-o", required=True, help="Результат пайплайна (output)")
    p_dreport.add_argument("--machine", "-m", choices=["laser_standard", "laser_80w", "impact"], default="laser_standard")
    p_dreport.add_argument("--face-mask", "-f", help="Маска лица (PNG)")
    p_dreport.add_argument("--subject-mask", "-s", help="Маска субъекта (PNG)")
    p_dreport.add_argument("--output-dir", "-d", help="Папка для отчётов (JSON+TXT+heatmap)")
    p_dreport.add_argument("--json", help="Путь для JSON отчёта")
    p_dreport.add_argument("--txt", help="Путь для текстового отчёта")
    p_dreport.add_argument("--heatmap", help="Путь для heatmap PNG")
    p_dreport.set_defaults(func=cmd_debug_report)

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

    # --list-presets как глобальный флаг
    if args.list_presets:
        cmd_list_presets(args)
        return

    _warmup_numba_if_needed(args)  # AUDIT-8.4: прогрев Numba JIT
    args.func(args)


if __name__ == "__main__":
    main()
