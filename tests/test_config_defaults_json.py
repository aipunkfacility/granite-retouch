"""Тест: config-defaults.json синхронизирован с Python DEFAULTS."""

import json
from pathlib import Path

from retouch.config import DEFAULTS


def _find_json_path() -> Path:
    """Найти config-defaults.json."""
    candidates = [
        Path(__file__).resolve().parent.parent
        / "retouch_ui" / "frontend" / "src" / "lib" / "config-defaults.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    pytest.skip("config-defaults.json не найден")


import pytest


class TestConfigDefaultsJson:
    """AUDIT-7.1: config-defaults.json синхронизирован с DEFAULTS."""

    def test_json_exists(self):
        """config-defaults.json файл существует."""
        json_path = _find_json_path()
        assert json_path.exists(), f"Файл не найден: {json_path}"

    def test_json_matches_defaults(self):
        """config-defaults.json содержит те же значения, что и DEFAULTS."""
        json_path = _find_json_path()
        with open(json_path, "r", encoding="utf-8") as f:
            json_defaults = json.load(f)

        # Рекурсивное сравнение
        _assert_dicts_equal(json_defaults, DEFAULTS, path="")

    def test_json_has_all_machine_types(self):
        """config-defaults.json содержит все три machine_type."""
        json_path = _find_json_path()
        with open(json_path, "r", encoding="utf-8") as f:
            json_defaults = json.load(f)

        for mtype in ("laser_standard", "laser_80w", "impact"):
            assert mtype in json_defaults["processing"], (
                f"Machine type {mtype} отсутствует в config-defaults.json"
            )


def _assert_dicts_equal(a, b, path=""):
    """Рекурсивно сравнить два dict, показывая путь к расхождению."""
    if isinstance(a, dict) and isinstance(b, dict):
        a_keys, b_keys = set(a.keys()), set(b.keys())
        if a_keys != b_keys:
            missing_in_a = b_keys - a_keys
            missing_in_b = a_keys - b_keys
            assert False, (
                f"Ключи расходятся на пути '{path}': "
                f"отсутствуют в JSON: {missing_in_b}, "
                f"отсутствуют в DEFAULTS: {missing_in_a}"
            )
        for key in a_keys:
            _assert_dicts_equal(a[key], b[key], path=f"{path}.{key}")
    elif a != b:
        assert False, (
            f"Значение расходится на пути '{path}': JSON={a!r}, DEFAULTS={b!r}"
        )
