#!/usr/bin/env python3
"""Migrate import paths after moving retouch/processing/*.py into subdirectories.

Usage:
    python scripts/migrate-processing-imports.py

Updates ALL .py files in the repo (excluding .venv, __pycache__, .git)
by replacing old flat import paths with new subdirectory paths per MODULE_MAP.
"""

import os
import sys

MODULE_MAP = {
    "pipeline": "core",
    "plan": "core",
    "gates": "core",
    "analysis": "analysis",
    "metrics": "analysis",
    "zones": "analysis",
    "levels": "correction",
    "face_correction": "correction",
    "glow": "correction",
    "unsharp": "correction",
    "shadow_noise": "correction",
    "gamma": "correction",
    "rolloff": "correction",
    "mask_utils": "correction",
    "face_region": "detection",
    "chromakey": "detection",
    "export": "output",
    "vignette": "output",
}

EXCLUDE_DIRS = {".venv", "__pycache__", ".git"}


def _should_exclude(dirpath: str) -> bool:
    parts = dirpath.replace("\\", "/").split("/")
    return any(p in EXCLUDE_DIRS for p in parts)


def _migrate_file(filepath: str) -> bool:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    for module, subdir in MODULE_MAP.items():
        # Pattern A: from retouch.processing.{module} import ...
        content = content.replace(
            f"from retouch.processing.{module} import",
            f"from retouch.processing.{subdir}.{module} import",
        )
        # Pattern B: import retouch.processing.{module} (with or without as)
        content = content.replace(
            f"import retouch.processing.{module}",
            f"import retouch.processing.{subdir}.{module}",
        )
        # Pattern C: from .{module} import ... (relative imports in __init__.py)
        content = content.replace(
            f"from .{module} import",
            f"from .{subdir}.{module} import",
        )

    if content == original:
        return False

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    changed: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if _should_exclude(dirpath):
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fn)
            if _migrate_file(filepath):
                changed.append(os.path.relpath(filepath, root))

    if changed:
        print(f"Updated {len(changed)} file(s):")
        for p in sorted(changed):
            print(f"  {p}")
    else:
        print("No files changed — all imports already match target paths.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
