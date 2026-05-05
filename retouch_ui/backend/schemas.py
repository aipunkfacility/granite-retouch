"""Pydantic-модели для REST API granite-retouch."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ─── Запросы ──────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Ответ POST /api/upload."""
    file_id: str = Field(..., description="UUID загрузки — используется для preview/export")
    filename: str = Field(..., description="Оригинальное имя файла")
    size_bytes: int = Field(..., description="Размер файла в байтах")


class PreviewRequest(BaseModel):
    """Запрос POST /api/process/preview."""
    file_id: str = Field(..., description="UUID загруженного файла")
    machine: str = Field("laser", pattern="^(laser|impact)$", description="Тип станка")
    params: Optional[dict] = Field(None, description="Параметры обработки (override config.yaml)")


class ExportRequest(BaseModel):
    """Запрос POST /api/process/export."""
    file_id: str = Field(..., description="UUID загруженного файла")
    machine: str = Field("laser", pattern="^(laser|impact)$")
    params: Optional[dict] = Field(None, description="Параметры обработки (override config.yaml)")
    format: str = Field("tiff", pattern="^(tiff|png)$", description="Формат экспорта")


class ConfigUpdateRequest(BaseModel):
    """Запрос PUT /api/config."""
    config: dict = Field(..., description="Полный конфиг или частичные изменения")


class PresetCreateRequest(BaseModel):
    """Запрос POST /api/presets."""
    name: str = Field(..., min_length=1, max_length=64, description="Имя пресета (без расширения)")
    config: dict = Field(..., description="Конфиг пресета")


class PresetDeleteRequest(BaseModel):
    """Запрос DELETE /api/presets/{name}."""
    name: str = Field(..., min_length=1, max_length=64)


# ─── Ответы ───────────────────────────────────────────────────────────

class PreviewResponse(BaseModel):
    """Ответ POST /api/process/preview — отдаётся как PNG-файл."""
    # На практике — FileResponse; схема нужна только для OpenAPI-документации
    pass


class DiagnosticsInfo(BaseModel):
    """Диагностика обработки — face_brightness, glow, black_ratio."""
    face_brightness_before: Optional[float] = None
    face_brightness_after: Optional[float] = None
    glow_size: Optional[int] = None
    glow_opacity: Optional[float] = None
    black_ratio: Optional[float] = None
    blue_ratio: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class ConfigResponse(BaseModel):
    """Ответ GET /api/config."""
    config: dict
    warnings: list[str] = Field(default_factory=list)


class ConfigUpdateResponse(BaseModel):
    """Ответ PUT /api/config."""
    saved: bool
    path: str = Field(..., description="Путь к сохранённому config.yaml")
    warnings: list[str] = Field(default_factory=list)


class DefaultsResponse(BaseModel):
    """Ответ GET /api/config/defaults."""
    defaults: dict


class PresetInfo(BaseModel):
    """Информация об одном пресете."""
    name: str
    config: dict


class PresetsListResponse(BaseModel):
    """Ответ GET /api/presets."""
    presets: list[PresetInfo]


class HealthResponse(BaseModel):
    """Ответ GET /api/health."""
    status: str = "ok"
    version: str = Field(..., description="Версия granite-retouch")


class ErrorResponse(BaseModel):
    """Общий формат ошибки."""
    detail: str
