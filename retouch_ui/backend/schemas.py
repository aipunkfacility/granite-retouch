"""Pydantic-модели для REST API granite-retouch."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ─── Валидация параметров обработки (D.4) ─────────────────────────────

class FaceOvalParams(BaseModel):
    """Параметры овала зоны лица (0-1 нормализованные координаты)."""
    cx: float = Field(0.5, ge=0.0, le=1.0, description="Центр X (0-1)")
    cy: float = Field(0.25, ge=0.0, le=1.0, description="Центр Y (0-1)")
    rx: float = Field(0.15, ge=0.01, le=0.50, description="Радиус X (0-1)")
    ry: float = Field(0.20, ge=0.01, le=0.50, description="Радиус Y (0-1)")
    source: str = Field("heuristic", pattern="^(heuristic|manual|auto|heuristic_legacy)$",
                        description="Источник овала")


class PreviewParams(BaseModel):
    """Валидированные параметры обработки (D.4).

    Все параметры опциональны — None означает «использовать из конфига».
    При передаче невалидного значения → 422 Validation Error.
    """
    brightness: Optional[float] = Field(None, ge=0.5, le=2.0,
                                        description="Множитель яркости (0.5–2.0)")
    glow_size: Optional[int] = Field(None, ge=5, le=100,
                                     description="Размер glow (5–100 px)")
    glow_opacity: Optional[int] = Field(None, ge=0, le=100,
                                        description="Непрозрачность glow (0–100%)")
    face_oval: Optional[FaceOvalParams] = Field(None,
                                                description="Овал зоны лица (нормализованный)")
    stone_type: Optional[str] = Field(None,
                                      pattern="^(granite|marble|gabbro|basalt)$",
                                      description="Тип камня")
    step_mm: Optional[float] = Field(None, ge=0.10, le=0.50,
                                     description="Шаг ЧПУ (мм)")
    highlight_start: Optional[int] = Field(None, ge=80, le=250,
                                           description="Порог затухания коррекции (80–250)")
    face_region_top: Optional[float] = Field(None, ge=0.2, le=0.8,
                                             description="Доля высоты для зоны лица (0.2–0.8)")
    legacy_step_order: Optional[bool] = Field(None,
                                              description="Старый порядок шагов (rollback)")


# ─── Запросы ──────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Ответ POST /api/upload."""
    file_id: str = Field(..., description="UUID загрузки — используется для preview/export")
    filename: str = Field(..., description="Оригинальное имя файла")
    size_bytes: int = Field(..., description="Размер файла в байтах")


class PreviewRequest(BaseModel):
    """Запрос POST /api/process/preview."""
    file_id: str = Field(..., description="UUID загруженного файла")
    machine: str = Field("laser_standard", pattern="^(laser_standard|laser_80w|impact)$",
                         description="Тип станка")
    params: Optional[PreviewParams] = Field(None,
                                            description="Валидированные параметры обработки")
    full_steps: bool = Field(True, description="D.3: true=все шаги, false=только final")


class ExportRequest(BaseModel):
    """Запрос POST /api/process/export."""
    file_id: str = Field(..., description="UUID загруженного файла")
    machine: str = Field("laser_standard", pattern="^(laser_standard|laser_80w|impact)$")
    params: Optional[PreviewParams] = Field(None,
                                            description="Валидированные параметры обработки")
    format: str = Field("bmp", pattern="^(bmp|bmp_1bit|bmp_8bit|png|tiff)$",
                        description="Формат экспорта")


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
