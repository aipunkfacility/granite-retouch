"""Роутер материала: профили, автокоррекция, валидация.

Эндпоинты:
  GET  /api/material/profiles  — MATERIAL_PROFILES для фронтенда
  POST /api/material/apply     — применить material overrides + validation + hint
"""

from __future__ import annotations

import copy
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from retouch.config import (
    MATERIAL_PROFILES,
    apply_material_overrides,
    validate_machine_material,
)

logger = logging.getLogger("retouch_ui.material")

router = APIRouter(prefix="/api", tags=["material"])


# ─── Схемы запросов/ответов ───────────────────────────────────────────


class MaterialApplyRequest(BaseModel):
    """Запрос POST /api/material/apply."""
    material: str = Field(
        ...,
        pattern="^(granite|marble|gabbro|basalt|acrylic)$",
        description="Тип материала",
    )
    machine_type: str = Field(
        ...,
        pattern="^(laser_standard|laser_80w|impact)$",
        description="Тип станка",
    )
    config: dict | None = Field(
        None,
        description="Текущий конфиг (для вычисления diffs). Если нет — используется DEFAULTS.",
    )


class MaterialApplyResponse(BaseModel):
    """Ответ POST /api/material/apply."""
    config_patch: dict = Field(
        default_factory=dict,
        description="Только изменённые ключи для deep_merge",
    )
    changes: list[dict] = Field(
        default_factory=list,
        description="Список автокоррекций из apply_material_overrides()",
    )
    validation_warnings: list[str] = Field(
        default_factory=list,
        description="WARNING/ERROR из validate_machine_material()",
    )
    active_hint: str | None = Field(
        None,
        description="Контекстная подсказка для текущей комбинации",
    )


class MaterialProfilesResponse(BaseModel):
    """Ответ GET /api/material/profiles."""
    profiles: dict = Field(
        default_factory=dict,
        description="MATERIAL_PROFILES — диапазоны, подсказки, hints",
    )


# ─── Эндпоинты ────────────────────────────────────────────────────────


@router.get("/material/profiles", response_model=MaterialProfilesResponse)
async def get_material_profiles():
    """Вернуть MATERIAL_PROFILES для фронтенда.

    Фронтенд вызывает один раз при загрузке и кэширует.
    Диапазоны, подсказки, hints — всё из бэкенда,
    фронтенд не дублирует бизнес-логику.
    """
    # Сериализуем tuple → list для JSON (step_mm_range, stone_gamma_range)
    serializable = {}
    for mat_key, profile in MATERIAL_PROFILES.items():
        entry = {}
        for k, v in profile.items():
            if isinstance(v, tuple):
                entry[k] = list(v)
            else:
                entry[k] = v
        serializable[mat_key] = entry

    return MaterialProfilesResponse(profiles=serializable)


@router.post("/material/apply", response_model=MaterialApplyResponse)
async def apply_material(request: MaterialApplyRequest):
    """Применить material overrides + validation + hint.

    Вызывается ПЕРЕД preview — оператор видит автокоррекции
    до запуска обработки и может отказаться от смены материала.
    """
    from retouch.config import DEFAULTS, deep_merge

    # 1. Собрать полный конфиг для применения overrides
    base_config = request.config if request.config else copy.deepcopy(DEFAULTS)
    base_config["machine_type"] = request.machine_type

    # Синхронизировать stone.type и stone.material
    stone = base_config.setdefault("stone", {})
    if "material" not in stone:
        stone["material"] = request.material
    stone["type"] = request.material
    stone["material"] = request.material

    # 2. Применить material overrides
    updated_config, changes = apply_material_overrides(base_config, request.material)

    # 3. Вычислить config_patch (только изменившиеся ключи)
    # Мы сравниваем updated_config с base_config на верхнем уровне
    # и собираем только изменившиеся ветки
    config_patch: dict = {}

    # stone — всегда обновляем material/type
    config_patch["stone"] = {
        "material": request.material,
        "type": request.material,
    }

    # processing — берём секцию machine_type если были изменения
    proc_updated = updated_config.get("processing", {}).get(request.machine_type, {})
    proc_original = base_config.get("processing", {}).get(request.machine_type, {})
    if proc_updated != proc_original:
        config_patch.setdefault("processing", {})[request.machine_type] = proc_updated

    # 4. Валидация совместимости
    validation_warnings = validate_machine_material(request.machine_type, request.material)

    # 5. Подсказка для текущей комбинации
    active_hint = _get_active_hint(request.material, request.machine_type)

    return MaterialApplyResponse(
        config_patch=config_patch,
        changes=changes,
        validation_warnings=validation_warnings,
        active_hint=active_hint,
    )


def _get_active_hint(material: str, machine_type: str) -> str | None:
    """Вычислить контекстную подсказку для комбинации материал+станок.

    Приоритет:
      1. Material hint для текущего machine_type
      2. Material notes
    """
    profile = MATERIAL_PROFILES.get(material, {})
    if not profile:
        return None

    hints = profile.get("hints", {})
    if hints and machine_type in hints:
        return hints[machine_type]

    notes = profile.get("notes")
    if notes:
        return notes

    return None
