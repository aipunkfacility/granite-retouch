import pytest
from retouch.processing.core.plan import (
    SafetyEnvelope, PipelinePlan, ValidatedPlan,
    validate_plan, PROFILE_STANDARD,
)


class TestSafetyEnvelopeFromConfig:
    def test_from_config_empty_uses_defaults(self):
        env = SafetyEnvelope.from_config({})
        assert env.face_skin_max_delta == 15.0
        assert env.face_dark_max_delta == 5.0
        assert env.hair_max_delta == 3.0
        assert env.clothes_max_delta == 0.0
        assert env.highlights_rolloff_only is True
        assert env.contour_inner_glow_only is True
        assert env.contour_outer_antifringe_only is True

    def test_from_config_none_uses_defaults(self):
        env = SafetyEnvelope.from_config()
        assert env.face_skin_max_delta == 15.0

    def test_from_config_partial_overrides(self):
        config = {"safety_envelope": {"face_skin_max_delta": 10.0, "hair_max_delta": 0.0}}
        env = SafetyEnvelope.from_config(config)
        assert env.face_skin_max_delta == 10.0
        assert env.hair_max_delta == 0.0
        assert env.face_dark_max_delta == 5.0  # default

    def test_from_config_all_overrides(self):
        config = {
            "safety_envelope": {
                "face_skin_max_delta": 8.0, "face_dark_max_delta": 3.0,
                "hair_max_delta": 0.0, "clothes_max_delta": 0.0,
            },
        }
        env = SafetyEnvelope.from_config(config)
        assert env.face_skin_max_delta == 8.0
        assert env.face_dark_max_delta == 3.0


class TestSafetyEnvelopeValidatePlan:
    def test_envelope_clips_skin_delta_positive(self):
        plan = PipelinePlan(profile=PROFILE_STANDARD, skin_delta=50.0)
        env = SafetyEnvelope(face_skin_max_delta=10.0)
        validated = validate_plan(plan, PROFILE_STANDARD, envelope=env)
        assert validated.plan.skin_delta == 10.0
        assert "skin_delta" in validated.clipped_params
        old, new = validated.clipped_params["skin_delta"]
        assert old == 50.0
        assert new == 10.0

    def test_envelope_clips_skin_delta_negative(self):
        plan = PipelinePlan(profile=PROFILE_STANDARD, skin_delta=-30.0)
        env = SafetyEnvelope(face_skin_max_delta=10.0)
        validated = validate_plan(plan, PROFILE_STANDARD, envelope=env)
        assert validated.plan.skin_delta == -10.0

    def test_envelope_does_not_clip_within_limit(self):
        plan = PipelinePlan(profile=PROFILE_STANDARD, skin_delta=5.0)
        env = SafetyEnvelope(face_skin_max_delta=15.0)
        validated = validate_plan(plan, PROFILE_STANDARD, envelope=env)
        assert validated.plan.skin_delta == 5.0
        assert len(validated.clipped_params) == 0

    def test_envelope_zero_delta_allowed(self):
        plan = PipelinePlan(profile=PROFILE_STANDARD, skin_delta=0.0)
        env = SafetyEnvelope(face_skin_max_delta=15.0)
        validated = validate_plan(plan, PROFILE_STANDARD, envelope=env)
        assert validated.plan.skin_delta == 0.0

    def test_envelope_no_envelope_does_not_clip(self):
        plan = PipelinePlan(profile=PROFILE_STANDARD, skin_delta=50.0)
        validated = validate_plan(plan, PROFILE_STANDARD, envelope=None)
        assert validated.plan.skin_delta == 50.0
        assert len(validated.clipped_params) == 0
