#!/usr/bin/env python3
"""Экспорт DEFAULTS из retouch/config.py в JSON для фронтенда.

Запуск: python scripts/export_defaults.py
Результат: retouch_ui/frontend/src/lib/config-defaults.json

Фронтенд использует этот файл для синхронизации дефолтных значений
с Python-бэкендом без ручного дублирования.

Режим --check: сравнить сгенерированный JSON с коммиченным файлом.
Используется в CI для обнаружения рассинхрона.
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
        f.write("\n")

    print(f"DEFAULTS exported to {output_path}")
    return output_path


def check_defaults_sync(json_path: Path | None = None) -> bool:
    """Проверить, что коммиченный JSON совпадает с Python DEFAULTS.

    Returns:
        bool: True если синхронизированы, False если есть рассинхрон.
    """
    if json_path is None:
        json_path = (
            PROJECT_ROOT
            / "retouch_ui"
            / "frontend"
            / "src"
            / "lib"
            / "config-defaults.json"
        )

    if not json_path.exists():
        print(f"FAIL: config-defaults.json не найден: {json_path}")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        committed = json.load(f)

    generated = json.loads(json.dumps(DEFAULTS, indent=2, ensure_ascii=False))

    if committed == generated:
        print(f"OK: config-defaults.json синхронизирован с DEFAULTS")
        return True
    else:
        print(f"FAIL: config-defaults.json рассинхронизирован с DEFAULTS")
        print(f"Запустите: python scripts/export_defaults.py")
        return False


if __name__ == "__main__":
    if "--check" in sys.argv:
        ok = check_defaults_sync()
        sys.exit(0 if ok else 1)
    else:
        export_defaults()
