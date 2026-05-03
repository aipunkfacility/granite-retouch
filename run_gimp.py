#!/usr/bin/env python3
"""run_gimp.py — backward-compatible wrapper.

Delegates to retouch.gimp.runner. Still works standalone
if retouch package is not installed (inline fallback removed in v2.3.0).

Usage:
    python run_gimp.py -i input.png -o output.tiff -m impact
"""

import sys

try:
    from retouch.cli import cmd_gimp
    import argparse

    # Replicate the original CLI interface
    parser = argparse.ArgumentParser(
        description="granite-retouch — запуск GIMP-постобработки"
    )
    parser.add_argument("--input", "-i", required=True,
        help="Путь к входному изображению (PNG с синим хромакеем)")
    parser.add_argument("--output", "-o", required=True,
        help="Путь к выходному файлу (TIFF)")
    parser.add_argument("--machine", "-m",
        choices=["laser", "impact"], default="laser",
        help="Тип станка гравировки (default: laser)")
    parser.add_argument("--config", "-c",
        help="Путь к config.yaml (default: auto-detect)")

    args = parser.parse_args()
    cmd_gimp(args)

except ImportError:
    print(
        "Error: retouch package not installed. Install with:\n"
        "  uv pip install -e .\n"
        "Or use the new CLI:\n"
        "  python -m retouch gimp -i input.png -o output.tiff -m impact",
        file=sys.stderr,
    )
    sys.exit(1)
