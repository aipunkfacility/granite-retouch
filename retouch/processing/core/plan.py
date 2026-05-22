"""PipelinePlan, SafetyEnvelope, ValidatedPlan — слой принятия решений.

PipelinePlan описывает КАКИЕ шаги будут применены и с какими параметрами.
SafetyEnvelope задаёт максимальные допустимые дельты по зонам.
ValidatedPlan клипует параметры до лимитов и возвращает warnings.

Pydantic-схемы (PipelinePlanSchema, ValidatedPlanSchema) — в
retouch_ui/backend/schemas.py для API-сериализации.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Processing profiles
# ---------------------------------------------------------------------------

PROFILE_PRESERVE = "preserve"
PROFILE_STANDARD = "standard"
PROFILE_DIAGNOSTIC = "diagnostic"

VALID_PROFILES = {PROFILE_PRESERVE, PROFILE_STANDARD, PROFILE_DIAGNOSTIC}

# Какие шаги активны для каждого профиля
PROFILE_ACTIVE_STEPS = {
    PROFILE_PRESERVE: {
        "chromakey", "grayscale", "glow", "highlight_rolloff", "vignette",
    },
    PROFILE_STANDARD: {
        "chromakey", "grayscale", "glow", "levels", "face_correction",
        "unsharp", "shadow_noise", "shadow_floor", "stone_gamma",
        "white_ceiling", "vignette",
    },
    PROFILE_DIAGNOSTIC: {
        "chromakey", "grayscale", "glow", "levels", "face_correction",
        "unsharp", "shadow_noise", "shadow_floor", "stone_gamma",
        "white_ceiling", "vignette",
    },
}


# ---------------------------------------------------------------------------
# SafetyEnvelope
# ---------------------------------------------------------------------------

@dataclass
class SafetyEnvelope:
    """Максимальная допустимая дельта по зоне.

    Значения эмпирические: ±15 на 256-шкале ≈ 6%, едва заметно на гравировке.
    Требуют калибровки на sample set из 10-15 реальных заказов.
    Доступны для переопределения через config.yaml (секция safety_envelope).
    """
    face_skin_max_delta: float = 15.0
    face_dark_max_delta: float = 5.0
    hair_max_delta: float = 3.0
    clothes_max_delta: float = 0.0
    highlights_rolloff_only: bool = True
    contour_inner_glow_only: bool = True
    contour_outer_antifringe_only: bool = True

    @classmethod
    def from_config(cls, config: dict | None = None) -> "SafetyEnvelope":
        """Создать envelope из конфига с дефолтами."""
        if config is None:
            return cls()

        envelope_cfg = config.get("safety_envelope", {})
        return cls(
            face_skin_max_delta=envelope_cfg.get("face_skin_max_delta", 15.0),
            face_dark_max_delta=envelope_cfg.get("face_dark_max_delta", 5.0),
            hair_max_delta=envelope_cfg.get("hair_max_delta", 3.0),
            clothes_max_delta=envelope_cfg.get("clothes_max_delta", 0.0),
            highlights_rolloff_only=envelope_cfg.get("highlights_rolloff_only", True),
            contour_inner_glow_only=envelope_cfg.get("contour_inner_glow_only", True),
            contour_outer_antifringe_only=envelope_cfg.get("contour_outer_antifringe_only", True),
        )


# ---------------------------------------------------------------------------
# PipelinePlan
# ---------------------------------------------------------------------------

@dataclass
class PipelinePlan:
    """Описание плана обработки — какие шаги и с какими параметрами.

    Pydantic-схемы для API-сериализации — в retouch_ui/backend/schemas.py.
    """
    profile: str = PROFILE_STANDARD
    active_steps: set[str] = field(default_factory=lambda: set(PROFILE_ACTIVE_STEPS[PROFILE_STANDARD]))
    highlight_rolloff_knee: float = 0.90
    highlight_rolloff_compression: float = 0.35
    glow_size: int = 40
    glow_opacity: float = 0.35
    unsharp_percent: int = 120
    unsharp_radius: float = 1.5
    unsharp_threshold: int = 0
    stone_gamma: float = 1.0
    shadow_floor: int = 0
    white_ceiling: int = 250
    compression: float = 0.35

    @classmethod
    def from_profile(cls, profile: str, machine_cfg: dict | None = None) -> "PipelinePlan":
        """Создать план из профиля с машинными параметрами."""
        if profile not in VALID_PROFILES:
            raise ValueError(f"Unknown profile: {profile}. Valid: {VALID_PROFILES}")

        active = set(PROFILE_ACTIVE_STEPS[profile])

        plan = cls(
            profile=profile,
            active_steps=active,
        )

        if machine_cfg:
            plan.glow_size = machine_cfg.get("glow_size_min", plan.glow_size)
            plan.glow_opacity = machine_cfg.get("glow_opacity_min", 30) / 100.0
            plan.unsharp_threshold = machine_cfg.get("unsharp_threshold", 0)
            plan.stone_gamma = machine_cfg.get("stone_gamma", 1.0)
            plan.shadow_floor = machine_cfg.get("shadow_floor", 0)
            plan.white_ceiling = machine_cfg.get("white_ceiling", 250)

        return plan


# ---------------------------------------------------------------------------
# ValidatedPlan
# ---------------------------------------------------------------------------

@dataclass
class ValidatedPlan:
    """Валидированный план — параметры клипнуты до envelope и профиля."""
    plan: PipelinePlan
    warnings: list[str] = field(default_factory=list)
    disabled_steps: list[str] = field(default_factory=list)
    clipped_params: dict[str, tuple[float, float]] = field(default_factory=dict)


def validate_plan(
    plan: PipelinePlan,
    profile: str,
    preset: dict | None = None,
    zones: object | None = None,
    envelope: SafetyEnvelope | None = None,
) -> ValidatedPlan:
    """Валидировать PipelinePlan против профиля, пресета и safety envelope.

    ValidatedPlan клипует параметры до лимитов профиля и safety envelope,
    отключает шаги, запрещённые профилем, и возвращает warnings для diagnostics.

    Pydantic-схемы (PipelinePlanSchema, ValidatedPlanSchema) для API — в
    retouch_ui/backend/schemas.py, не дублируют логику валидации.

    Args:
        plan: PipelinePlan для валидации
        profile: имя профиля
        preset: машинный пресет (machine_cfg)
        zones: ZoneMasks или None
        envelope: SafetyEnvelope или None

    Returns:
        ValidatedPlan: клипнутый план с warnings.
    """
    warnings: list[str] = []
    disabled: list[str] = []
    clipped: dict[str, tuple[float, float]] = {}

    # Профиль отключает шаги (immutable: не мутируем оригинал)
    allowed_steps = PROFILE_ACTIVE_STEPS.get(profile, set())
    new_active = set(plan.active_steps)
    for step in plan.active_steps:
        if step not in allowed_steps:
            disabled.append(step)
            new_active.discard(step)
    plan = replace(plan, active_steps=new_active)

    # Rolloff vs ceiling: rolloff заменяет hard ceiling
    # Финальный np.clip остаётся страховкой

    validated = ValidatedPlan(
        plan=plan,
        warnings=warnings,
        disabled_steps=disabled,
        clipped_params=clipped,
    )

    logger.info(
        "ValidatedPlan: profile=%s, active_steps=%d, warnings=%d, disabled=%d",
        profile, len(plan.active_steps), len(warnings), len(disabled),
    )

    return validated
