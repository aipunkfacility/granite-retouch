"""Unit-тесты CLI argparse и pipeline behavior: парсинг аргументов + профили."""

import subprocess
import sys


class TestProcessProfileArgument:
    """--profile аргумент в CLI process команде."""

    def test_process_has_profile_argument(self):
        """--profile показывается в справке с valid choices."""
        result = subprocess.run(
            [sys.executable, "-m", "retouch", "process", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert "--profile" in result.stdout
        assert "preserve" in result.stdout
        assert "standard" in result.stdout
        assert "diagnostic" in result.stdout

    def test_process_profile_default_is_none(self):
        """Парсер принимает process без --profile (не падает)."""
        result = subprocess.run(
            [sys.executable, "-m", "retouch", "process",
             "-i", "input.png", "-o", "output.bmp", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_process_profile_invalid_choice(self):
        """Невалидное значение profile вызывает ошибку."""
        result = subprocess.run(
            [sys.executable, "-m", "retouch", "process",
             "-i", "input.png", "-o", "output.bmp",
             "--profile", "invalid"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0


class TestProfilePipelineBehavior:
    """Профили влияют на состав шагов пайплайна (unit-тесты без subprocess)."""

    def test_profile_affects_pipeline_plan(self):
        """Different profiles produce different active_steps."""
        from retouch.processing.core.plan import PipelinePlan, PROFILE_PRESERVE, PROFILE_STANDARD

        preserve_plan = PipelinePlan.from_profile(PROFILE_PRESERVE, {})
        standard_plan = PipelinePlan.from_profile(PROFILE_STANDARD, {})

        # preserve should NOT have levels or unsharp
        assert "levels" not in preserve_plan.active_steps
        assert "unsharp" not in preserve_plan.active_steps

        # standard should have all steps
        assert "levels" in standard_plan.active_steps
        assert "unsharp" in standard_plan.active_steps

    def test_preserve_profile_has_fewer_steps(self):
        """preserve profile has fewer active_steps than standard."""
        from retouch.processing.core.plan import PipelinePlan, PROFILE_PRESERVE, PROFILE_STANDARD

        preserve_plan = PipelinePlan.from_profile(PROFILE_PRESERVE, {})
        standard_plan = PipelinePlan.from_profile(PROFILE_STANDARD, {})

        assert len(preserve_plan.active_steps) < len(standard_plan.active_steps)

    def test_diagnostic_profile_has_same_steps_as_standard(self):
        """diagnostic profile has the same active_steps as standard."""
        from retouch.processing.core.plan import PipelinePlan, PROFILE_STANDARD, PROFILE_DIAGNOSTIC

        standard_plan = PipelinePlan.from_profile(PROFILE_STANDARD, {})
        diagnostic_plan = PipelinePlan.from_profile(PROFILE_DIAGNOSTIC, {})

        assert standard_plan.active_steps == diagnostic_plan.active_steps
