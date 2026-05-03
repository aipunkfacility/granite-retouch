#!/usr/bin/env python3
"""prepare_vignette.py — backward-compatible wrapper.

Delegates to retouch.processing.pipeline. Still works standalone
if retouch package is not installed (inline fallback removed in v2.3.0).

Usage:
    python prepare_vignette.py -i input.png -o output.tiff -m laser
"""

import sys

try:
    from retouch.cli import cmd_process
    from retouch.config import load_config
    import argparse

    # Replicate the original CLI interface
    parser = argparse.ArgumentParser(
        description="granite-retouch — подготовка файла для гравировки"
    )
    parser.add_argument("--input", "-i", required=True,
        help="Путь к входному изображению (PNG с синим хромакеем)")
    parser.add_argument("--output", "-o", required=True,
        help="Путь к выходному файлу (TIFF)")
    parser.add_argument("--machine", "-m",
        choices=["laser", "impact"], default="laser",
        help="Тип станка гравировки (default: laser)")
    parser.add_argument("--glow-size", type=int,
        help="Переопределить размер Inner Glow (px)")
    parser.add_argument("--glow-opacity", type=int,
        help="Переопределить opacity Inner Glow (%%)")
    parser.add_argument("--config", "-c",
        help="Путь к config.yaml (default: auto-detect)")
    parser.add_argument("--no-validate", action="store_true",
        help="Пропустить валидацию входного изображения и результата")

    args = parser.parse_args()
    cmd_process(args)

except ImportError:
    print(
        "Error: retouch package not installed. Install with:\n"
        "  uv pip install -e .\n"
        "Or use the new CLI:\n"
        "  python -m retouch process -i input.png -o output.tiff -m laser",
        file=sys.stderr,
    )
    sys.exit(1)
