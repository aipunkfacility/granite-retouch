"""Роутер конфигурации: чтение, обновление, дефолты."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from retouch.config import (
    DEFAULTS,
    _migrate_face_target,
    _run_migrations,
    deep_merge,
    find_config_path,
    load_config,
    validate_config,
)

from ..schemas import (
    ConfigResponse,
    ConfigUpdateRequest,
    ConfigUpdateResponse,
    DefaultsResponse,
)

logger = logging.getLogger("retouch_ui.config")

router = APIRouter(prefix="/api", tags=["config"])

# Корневая директория проекта — для проверки containment путей
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _validate_path_containment(path: Path) -> Path:
    """Проверить, что путь находится внутри корня проекта.

    resolve() раскрывает symlink'и и .. — защита от path traversal.
    startswith() проверяет, что итоговый путь внутри проекта.

    Raises:
        HTTPException: если путь выходит за пределы проекта
    """
    resolved = path.resolve()
    if not str(resolved).startswith(str(_PROJECT_ROOT)):
        raise HTTPException(
            403,
            f"Путь {resolved} выходит за пределы проекта {_PROJECT_ROOT}. "
            f"Path traversal заблокирован.",
        )
    return resolved


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Получить текущую конфигурацию проекта."""
    try:
        config = load_config()
        warnings = validate_config(config)
        return ConfigResponse(config=config, warnings=warnings)
    except Exception as exc:
        logger.exception("Ошибка чтения конфигурации: %s", exc)
        raise HTTPException(500, f"Ошибка чтения конфигурации: {exc}")


@router.put("/config", response_model=ConfigUpdateResponse)
async def update_config(request: ConfigUpdateRequest):
    """Обновить конфигурацию проекта.

    A3 CRITICAL: deep_merge с DEFAULTS — не теряем ключи, которых нет в запросе.
    Фронтенд может отправить неполный конфиг (только изменённые параметры)
    или полный — в обоих случаях DEFAULTS заполнят отсутствующие ключи.
    """
    # deep_merge с DEFAULTS — не теряем ключи, которых нет в запросе
    full_config = deep_merge(DEFAULTS, request.config)

    # Миграция устаревших ключей (brightness → stone_gamma, и т.д.)
    full_config = _run_migrations(full_config)

    # Валидация объединённого конфига
    warnings = validate_config(full_config)

    # Определить путь сохранения
    config_path = find_config_path()
    if config_path is None:
        config_path = Path.cwd() / "config.yaml"

    # Безопасность: проверить, что путь внутри проекта
    config_path = _validate_path_containment(config_path)

    # Сохранить
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(full_config, f, default_flow_style=False, allow_unicode=True)
        logger.info("Config saved to %s", config_path)
    except Exception as exc:
        logger.exception("Ошибка сохранения конфигурации: %s", exc)
        raise HTTPException(500, f"Ошибка сохранения: {exc}")

    return ConfigUpdateResponse(saved=True, path=str(config_path), warnings=warnings)


@router.get("/config/defaults", response_model=DefaultsResponse)
async def get_defaults():
    """Получить дефолтную конфигурацию (DEFAULTS из config.py)."""
    return DefaultsResponse(defaults=DEFAULTS)
