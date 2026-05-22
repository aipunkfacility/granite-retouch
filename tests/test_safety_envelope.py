import pytest
from retouch.processing.core.plan import (
    SafetyEnvelope,
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


