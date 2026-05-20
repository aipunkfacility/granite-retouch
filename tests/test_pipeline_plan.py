"""Тесты для модуля plan.py — PipelinePlan, SafetyEnvelope, ValidatedPlan."""

import pytest

from retouch.processing.core.plan import (
    PipelinePlan,
    ValidatedPlan,
    SafetyEnvelope,
    validate_plan,
    PROFILE_PRESERVE,
    PROFILE_STANDARD,
    PROFILE_DIAGNOSTIC,
    VALID_PROFILES,
    PROFILE_ACTIVE_STEPS,
)


class TestPipelinePlanDefaults:
    """PipelinePlan construct с дефолтами."""

    def test_pipeline_plan_constructs_with_defaults(self):
        """PipelinePlan создаётся с дефолтами."""
        plan = PipelinePlan()
        assert plan.profile == PROFILE_STANDARD
        assert plan.active_steps == PROFILE_ACTIVE_STEPS[PROFILE_STANDARD]

    def test_pipeline_plan_active_steps_dict(self):
        """active_steps задаёт множество шагов."""
        plan = PipelinePlan.from_profile(PROFILE_PRESERVE)
        assert "levels" not in plan.active_steps
        assert "unsharp" not in plan.active_steps
        assert "glow" in plan.active_steps

    def test_pipeline_plan_profiles_orthogonal_to_presets(self):
        """Профиль не зависит от пресета."""
        plan_std = PipelinePlan.from_profile(PROFILE_STANDARD, {"stone_gamma": 0.88})
        plan_pre = PipelinePlan.from_profile(PROFILE_PRESERVE, {"stone_gamma": 0.88})
        assert plan_std.active_steps != plan_pre.active_steps
        assert plan_std.stone_gamma == plan_pre.stone_gamma


class TestProfiles:
    """Профили обработки."""

    def test_profile_preserve_disables_levels_and_unsharp(self):
        """Preserve отключает levels и unsharp."""
        plan = PipelinePlan.from_profile(PROFILE_PRESERVE)
        assert "levels" not in plan.active_steps
        assert "unsharp" not in plan.active_steps
        assert "face_correction" not in plan.active_steps

    def test_profile_standard_matches_current_behavior(self):
        """Standard сохраняет текущую логику."""
        plan = PipelinePlan.from_profile(PROFILE_STANDARD)
        assert "levels" in plan.active_steps
        assert "face_correction" in plan.active_steps
        assert "unsharp" in plan.active_steps

    def test_profile_diagnostic_keeps_intermediates(self):
        """Diagnostic сохраняет все шаги."""
        plan = PipelinePlan.from_profile(PROFILE_DIAGNOSTIC)
        assert plan.active_steps == PROFILE_ACTIVE_STEPS[PROFILE_DIAGNOSTIC]

    def test_unknown_profile_raises(self):
        """Неизвестный профиль вызывает ValueError."""
        with pytest.raises(ValueError, match="Unknown profile"):
            PipelinePlan.from_profile("unknown")


class TestSafetyEnvelope:
    """SafetyEnvelope лимиты."""

    def test_envelope_face_skin_delta_max_15(self):
        """Envelope ограничивает face_skin ±15."""
        env = SafetyEnvelope()
        assert env.face_skin_max_delta == 15.0

    def test_envelope_face_dark_delta_max_5(self):
        """Envelope ограничивает face_dark ±5."""
        env = SafetyEnvelope()
        assert env.face_dark_max_delta == 5.0

    def test_envelope_clothes_zero_delta(self):
        """Clothes не допускает изменение по решению лица."""
        env = SafetyEnvelope()
        assert env.clothes_max_delta == 0.0

    def test_envelope_highlights_rolloff_only(self):
        """Highlights допускает только rolloff."""
        env = SafetyEnvelope()
        assert env.highlights_rolloff_only is True

    def test_envelope_from_config_yaml(self):
        """Envelope читается из конфига."""
        config = {
            "safety_envelope": {
                "face_skin_max_delta": 20.0,
                "face_dark_max_delta": 10.0,
            }
        }
        env = SafetyEnvelope.from_config(config)
        assert env.face_skin_max_delta == 20.0
        assert env.face_dark_max_delta == 10.0

    def test_envelope_degradation_contract(self):
        """Ненадёжная маска деградирует в менее агрессивную зону."""
        env = SafetyEnvelope()
        assert env.clothes_max_delta == 0.0
        assert env.hair_max_delta <= env.face_skin_max_delta


class TestValidatePlan:
    """ValidatedPlan валидация."""

    def test_validate_plan_clips_skin_delta(self):
        """skin_delta=50 клипуется до max_skin_delta."""
        plan = PipelinePlan(skin_delta=50.0)
        env = SafetyEnvelope(face_skin_max_delta=15.0)
        result = validate_plan(plan, PROFILE_STANDARD, envelope=env)
        assert plan.skin_delta == 15.0
        assert len(result.warnings) > 0
        assert "skin_delta" in result.clipped_params

    def test_validate_plan_preserve_disables_unsharp(self):
        """Preserve + unsharp_percent > 0 отключает unsharp."""
        plan = PipelinePlan(
            profile=PROFILE_PRESERVE,
            active_steps={"chromakey", "grayscale", "glow", "unsharp"},
            unsharp_percent=120,
        )
        result = validate_plan(plan, PROFILE_PRESERVE)
        assert "unsharp" not in plan.active_steps
        assert "unsharp" in result.disabled_steps

    def test_validate_plan_rolloff_vs_ceiling(self):
        """Rolloff и ceiling конфликт решается в пользу rolloff."""
        plan = PipelinePlan(
            highlight_rolloff_knee=0.90,
            highlight_rolloff_compression=0.35,
            white_ceiling=250,
        )
        result = validate_plan(plan, PROFILE_STANDARD)
        assert result.plan.highlight_rolloff_knee == 0.90

    def test_validate_plan_returns_warnings(self):
        """Клипнутые параметры видны в warnings."""
        plan = PipelinePlan(skin_delta=50.0)
        env = SafetyEnvelope(face_skin_max_delta=15.0)
        result = validate_plan(plan, PROFILE_STANDARD, envelope=env)
        assert any("skin_delta" in w for w in result.warnings)

    def test_invalid_plan_does_not_reach_pixel_ops(self):
        """Невалидный план не проходит в pixel operations."""
        plan = PipelinePlan(profile="invalid", active_steps=set())
        result = validate_plan(plan, "invalid")
        # Invalid profile results in empty active_steps
        assert len(result.plan.active_steps) == 0
