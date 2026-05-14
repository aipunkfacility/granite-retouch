"""Роутер пресетов: список, создание, удаление."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from retouch.config import find_config_path

from ..schemas import (
    PresetCreateRequest,
    PresetInfo,
    PresetsListResponse,
)

logger = logging.getLogger("retouch_ui.presets")

router = APIRouter(prefix="/api", tags=["presets"])

_PRESET_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_preset_name(name: str) -> str:
    """Whitelist-валидация: только латиница, цифры, дефис, подчёркивание."""
    if not _PRESET_NAME_RE.match(name):
        raise HTTPException(400,
            "Недопустимое имя пресета. Допустимы: латиница, цифры, '-', '_'")
    return name


def _presets_dir() -> Path:
    """Директория с YAML-пресетами.

    A11: Использует find_config_path() как якорь вместо хрупкой
    навигации по 4 уровням __file__.parent.
    config.yaml находится в корне проекта → config_path.parent = корень проекта.
    """
    config_path = find_config_path()
    if config_path:
        return config_path.parent / "presets"
    return Path.cwd() / "presets"


def _ensure_presets_dir() -> Path:
    """Убедиться, что директория пресетов существует, и вернуть путь."""
    d = _presets_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/presets/catalog")
async def get_presets_catalog():
    """Вернуть PRESET_CATALOG — UI-метаданные (бренд, категория, alert)."""
    from retouch.presets_catalog import PRESET_CATALOG
    return {"catalog": PRESET_CATALOG}


@router.get("/presets", response_model=PresetsListResponse)
async def list_presets():
    """Получить список всех пресетов."""
    presets_dir = _presets_dir()
    if not presets_dir.exists():
        return PresetsListResponse(presets=[])

    presets = []
    for p in sorted(presets_dir.glob("*.yaml")):
        try:
            with open(p, "r") as f:
                config = yaml.safe_load(f)
            if isinstance(config, dict):
                presets.append(PresetInfo(name=p.stem, config=config))
        except Exception as exc:
            logger.warning("Не удалось прочитать пресет %s: %s", p, exc)

    return PresetsListResponse(presets=presets)


@router.post("/presets", response_model=PresetInfo)
async def create_preset(request: PresetCreateRequest):
    """Создать новый пресет."""
    # Валидация имени — whitelist
    safe_name = _validate_preset_name(request.name)

    presets_dir = _ensure_presets_dir()
    preset_path = presets_dir / f"{safe_name}.yaml"

    if preset_path.exists():
        raise HTTPException(409, f"Пресет '{safe_name}' уже существует")

    try:
        with open(preset_path, "w") as f:
            yaml.dump(request.config, f, default_flow_style=False, allow_unicode=True)
        logger.info("Пресет создан: %s", preset_path)
    except Exception as exc:
        raise HTTPException(500, f"Ошибка сохранения пресета: {exc}")

    return PresetInfo(name=safe_name, config=request.config)


@router.delete("/presets/{name}")
async def delete_preset(name: str):
    """Удалить пресет по имени."""
    # Валидация имени — whitelist
    safe_name = _validate_preset_name(name)
    preset_path = _presets_dir() / f"{safe_name}.yaml"

    if not preset_path.exists():
        raise HTTPException(404, f"Пресет '{safe_name}' не найден")

    try:
        preset_path.unlink()
        logger.info("Пресет удалён: %s", preset_path)
    except Exception as exc:
        raise HTTPException(500, f"Ошибка удаления пресета: {exc}")

    return {"deleted": safe_name}
