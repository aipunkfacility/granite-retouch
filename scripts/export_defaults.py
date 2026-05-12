#!/usr/bin/env python3
"""Экспорт DEFAULTS из retouch/config.py в JSON для фронтенда.

Запуск: python scripts/export_defaults.py
Результат: retouch_ui/frontend/src/lib/config-defaults.json

Фронтенд использует этот файл для синхронизации дефолтных значений
с Python-бэкендом без ручного дублирования.
"""

import json
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from retouch.config import DEFAULTS  # noqa: E402


def export_defaults(output_path: Path | None = None) -> Path:
    """Экспортировать DEFAULTS в JSON-файл.

    Args:
        output_path: путь к выходному файлу. По умолчанию —
            retouch_ui/frontend/src/lib/config-defaults.json

    Returns:
        Path: путь к созданному файлу
    """
    if output_path is None:
        output_path = (
            PROJECT_ROOT
            / "retouch_ui"
            / "frontend"
            / "src"
            / "lib"
            / "config-defaults.json"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(DEFAULTS, f, indent=2, ensure_ascii=False)

    print(f"DEFAULTS exported to {output_path}")
    return output_path


if __name__ == "__main__":
    export_defaults()
