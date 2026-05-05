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


class VignetteMaskRequest(BaseModel):
    """Запрос POST /api/vignette/mask."""
    width: int = Field(..., ge=64, le=4096, description="Ширина маски (пиксели)")
    height: int = Field(..., ge=64, le=4096, description="Высота маски (пиксели)")
    vignette: dict = Field(..., description="Параметры виньетки из config.yaml")


# ─── Ответы ───────────────────────────────────────────────────────────

class PreviewDiagnostics(BaseModel):
    """Диагностика обработки — face_brightness, glow, black_ratio."""
    glow_size: int = 0
    glow_opacity: float = 0.0
    face_brightness_before: float = 0.0
    face_brightness_after: float = 0.0
    face_correction_factor: float = 0.0
    black_ratio: float = 0.0
    blue_ratio: float = 0.0
    width: int = 0
    height: int = 0


class PreviewResponse(BaseModel):
    """Ответ POST /api/process/preview — JSON с base64-картинками + диагностика."""
    images: dict[str, str] = Field(
        default_factory=dict,
        description="Шаги обработки → data:image/png;base64,...",
    )
    diagnostics: PreviewDiagnostics = Field(default_factory=PreviewDiagnostics)
    warnings: list[str] = Field(default_factory=list)


class DiagnosticsInfo(BaseModel):
    """Диагностика обработки — face_brightness, glow, black_ratio (legacy)."""
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


class VignetteMaskParams(BaseModel):
    """Вычисленные параметры эллипса виньетки."""
    arch_top_y: float = Field(..., description="Верх арки (пиксели)")
    arch_bottom_y: float = Field(..., description="Низ арки (пиксели)")
    h_oversize: float = Field(..., description="Горизонтальный оверсайз (пиксели)")


class VignetteMaskResponse(BaseModel):
    """Ответ POST /api/vignette/mask."""
    mask: str = Field(..., description="data:image/png;base64,... арховая маска")
    params: VignetteMaskParams = Field(..., description="Вычисленные параметры эллипса")
