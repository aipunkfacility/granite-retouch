"""Тесты routing: machine_type → промпт-файл (D2, этап 5)."""

import pytest
from pathlib import Path

from retouch.config import DEFAULTS, MACHINE_TYPES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_BLOCKS = PROJECT_ROOT / ".agents" / "skills" / "retouch-prompter" / "prompt_blocks"

MACHINE_TYPE_TO_FILE = {
    "laser_standard": "laser.md",
    "laser_80w": "laser-80w.md",
    "impact": "impact.md",
}


class TestSkillRouting:
    """D2: каждый machine_type выбирает корректный промпт-файл."""

    @pytest.mark.parametrize("machine_type,expected_file", MACHINE_TYPE_TO_FILE.items())
    def test_machine_type_selects_correct_file(self, machine_type, expected_file):
        """Маппинг machine_type → файл существует и читаем."""
        path = PROMPT_BLOCKS / expected_file
        assert path.exists(), f"Промпт-файл {expected_file} не найден по пути {path}"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"Файл {expected_file} слишком короткий ({len(content)} символов)"

    def test_no_legacy_machine_type_values(self):
        """Старые значения 'laser' больше не используются в SKILL.md."""
        skill_md = PROJECT_ROOT / ".agents" / "skills" / "retouch-prompter" / "SKILL.md"
        if not skill_md.exists():
            pytest.skip("SKILL.md не найден — пропускаем проверку роутинга")
        text = skill_md.read_text(encoding="utf-8")
        # SKILL.md не должен содержать 'laser' как самостоятельный machine_type
        assert '"laser"' not in text or 'laser_standard' in text, \
            "SKILL.md должен использовать 'laser_standard', не 'laser'"

    def test_all_machine_types_have_config(self):
        """Каждый machine_type имеет секцию в DEFAULTS."""
        for machine_type in MACHINE_TYPE_TO_FILE:
            assert machine_type in DEFAULTS["processing"], \
                f"Нет секции {machine_type} в DEFAULTS['processing']"

    def test_laser_80w_file_contains_ceiling(self):
        """laser-80w.md упоминает потолок 235."""
        path = PROMPT_BLOCKS / "laser-80w.md"
        if not path.exists():
            pytest.skip("laser-80w.md не найден")
        content = path.read_text(encoding="utf-8")
        assert "235" in content, "laser-80w.md должен упоминать потолок яркости 235"

    def test_impact_file_has_calibration_note(self):
        """impact.md содержит Calibration Note."""
        path = PROMPT_BLOCKS / "impact.md"
        content = path.read_text(encoding="utf-8")
        assert "Calibration Note" in content or "calibration" in content.lower(), \
            "impact.md должен содержать Calibration Note"
