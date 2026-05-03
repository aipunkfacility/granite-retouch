#!/usr/bin/env python3
"""granite-retouch — единая точка входа CLI.

Команды:
  python -m retouch process -i ... -o ... -m laser   # Pillow-обработка
  python -m retouch validate -i ai.png                # Валидация изображения
  python -m retouch gimp -i ... -o ... -m impact      # GIMP-обработка
"""

import argparse
import os
import sys

from retouch.config import load_config
from retouch.validation.image import ValidationError


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
    """GIMP-обработка портрета."""
    from retouch.gimp.runner import run_gimp

    config = load_config(args.config)

    if not os.path.isfile(args.input):
        print(f"Error: входной файл не найден: {args.input}", file=sys.stderr)
        sys.exit(1)

    exit_code = run_gimp(args.input, args.output, machine_type=args.machine, config=config)
    if exit_code == 0:
        print("GIMP processing complete.")
    sys.exit(exit_code)


def main():
    parser = argparse.ArgumentParser(
        prog="retouch",
        description="granite-retouch — AI-ретушь портретов для гравировки"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- process ---
    p_process = subparsers.add_parser("process", help="Pillow-обработка портрета")
    p_process.add_argument("--input", "-i", required=True, help="Входной PNG (с хромакеем)")
    p_process.add_argument("--output", "-o", required=True, help="Выходной TIFF")
    p_process.add_argument("--machine", "-m", choices=["laser", "impact"], default="laser")
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
    p_gimp = subparsers.add_parser("gimp", help="GIMP-обработка портрета")
    p_gimp.add_argument("--input", "-i", required=True, help="Входной PNG")
    p_gimp.add_argument("--output", "-o", required=True, help="Выходной TIFF")
    p_gimp.add_argument("--machine", "-m", choices=["laser", "impact"], default="laser")
    p_gimp.add_argument("--config", "-c", help="Путь к config.yaml")
    p_gimp.set_defaults(func=cmd_gimp)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
