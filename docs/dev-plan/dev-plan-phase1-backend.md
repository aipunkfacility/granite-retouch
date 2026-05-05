# Фаза 1: FastAPI Backend API

**Предыдущий этап**: [Фаза 0](dev-plan-phase0-pipeline.md)
**Следующий этап**: [Фаза 2](dev-plan-phase2-frontend.md) (можно параллелить)
**Время**: 6–8 часов
**Цель**: Создать FastAPI sidecar-бэкенд, который предоставляет REST API для загрузки изображений, предпросмотра, экспорта, управления конфигурацией и пресетами. Бэкенд работает на `localhost:8001` и использует `asyncio.to_thread` для CPU-bound обработки Pillow/numpy.

---

## Зависимости от предыдущих фаз

| Зависимость | Фаза | Статус |
|-------------|------|--------|
| `process_steps()`, `process_preview()`, `process_export()` | Фаза 0 | Должны быть реализованы |
| `PipelineResult` с `release_intermediates()` | Фаза 0 | Должен быть реализован |
| `deep_merge()`, `load_config()`, `validate_config()`, `DEFAULTS`, `find_config_path()` | Фаза 0 | Должны быть реализованы |
| Pydantic-модель `RetouchConfig` в `retouch/config.py` | Фаза 0 | Должна быть реализована |
| Версия `3.0.0-dev` в `retouch/__init__.py` | Pre-0 | Должна быть установлена |

> ⚠ **Блокировка**: Если Фаза 0 не завершена (нет `git tag phase0-done`), задачи 3–6 данной фазы не могут быть реализованы. Задачи 1–2 (schemas.py, main.py) можно начать параллельно, используя мок-импорты.

---

## Структура файлов (итог Фазы 1)

```
retouch_ui/
├── __init__.py                     # ПУСТОЙ (A13)
├── backend/
│   ├── __init__.py                 # ПУСТОЙ (A13)
│   ├── main.py                     # FastAPI app + lifespan + CORS
│   ├── schemas.py                  # Pydantic-модели запросов/ответов
│   ├── routers/
│   │   ├── __init__.py             # ПУСТОЙ (A13)
│   │   ├── process.py              # /upload, /process/preview, /process/export
│   │   ├── config.py               # GET/PUT /config, /config/defaults (A3: deep_merge)
│   │   └── presets.py              # GET/POST/DELETE /presets (A11: find_config_path)
│   └── requirements.txt            # зависимости бэкенда
```

---

## Задачи

### 1. Создать `__init__.py` для retouch_ui (A13)

**Обоснование**: Без `__init__.py` в `retouch_ui/`, `retouch_ui/backend/` и `retouch_ui/backend/routers/` невозможно использовать relative imports в `conftest.py` (Фаза 4) и корректную установку пакета через `pip install -e .`.

**Файлы**:

`retouch_ui/__init__.py`:
```python
# Пустой файл — делает retouch_ui Python-пакетом.
# Необходим для relative imports в conftest.py и pip install -e .
```

`retouch_ui/backend/__init__.py`:
```python
# Пустой файл — делает retouch_ui/backend Python-пакетом.
```

`retouch_ui/backend/routers/__init__.py`:
```python
# Пустой файл — делает retouch_ui/backend/routers Python-пакетом.
```

**Проверка**: `python -c "from retouch_ui.backend.routers import process"` — не должно быть ImportError.

---

### 2. Создать `schemas.py` — Pydantic-модели

**Файл**: `retouch_ui/backend/schemas.py`
**Обоснование**: Единый источник истины для типов запросов и ответов API. Pydantic обеспечивает валидацию, сериализацию и автогенерацию OpenAPI-схемы.

```python
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
    face_brightness: Optional[float] = None
    glow_value: Optional[float] = None
    black_ratio: Optional[float] = None
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
```

**Проверка**: `python -c "from retouch_ui.backend.schemas import HealthResponse; print(HealthResponse(status='ok', version='3.0.0-dev'))"`.

---

### 3. Создать `routers/process.py` — загрузка, предпросмотр, экспорт

**Файл**: `retouch_ui/backend/routers/process.py`
**Обоснование**: Основной функциональный роутер. Загрузка изображения один раз, предпросмотр по `file_id`, экспорт в полном разрешении. `asyncio.to_thread` — CPU-bound Pillow не блокирует event loop.

```python
"""Роутер обработки изображений: загрузка, предпросмотр, экспорт."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Tuple

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from retouch.config import load_config, find_config_path
from retouch.processing.pipeline import (
    process_preview,
    process_export,
    PreviewResult,
)

from ..schemas import (
    UploadResponse,
    PreviewRequest,
    ExportRequest,
    DiagnosticsInfo,
)

logger = logging.getLogger("retouch_ui.process")

router = APIRouter(prefix="/api", tags=["process"])

# ─── Хранилище загруженных файлов ─────────────────────────────────────
# Ключ: file_id (UUID), значение: (путь к файлу, оригинальное имя)
_uploaded_files: Dict[str, Tuple[Path, str]] = {}

MAX_UPLOADED_FILES = 50  # A16: лимит на количество одновременно загруженных файлов


def _cleanup_uploaded(file_id: str) -> None:
    """Удалить временный файл загрузки. Вызывается через BackgroundTask или TTL."""
    entry = _uploaded_files.pop(file_id, None)
    if entry is None:
        return
    path, _ = entry
    try:
        if path.exists():
            path.unlink()
            logger.debug("Удалён временный файл: %s", path)
    except OSError as exc:
        logger.warning("Не удалось удалить %s: %s", path, exc)


async def _ttl_cleanup() -> None:
    """Фоновая корутина: удалять файлы старше 30 минут."""
    import time

    MAX_AGE_SEC = 1800  # 30 минут

    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired = []
        for fid, (path, _) in _uploaded_files.items():
            try:
                if path.exists() and (now - path.stat().st_mtime) > MAX_AGE_SEC:
                    expired.append(fid)
            except OSError:
                expired.append(fid)
        for fid in expired:
            _cleanup_uploaded(fid)
            logger.info("TTL-очистка: удалён file_id=%s", fid)


# ─── Эндпоинты ────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Загрузить изображение на сервер. Возвращает file_id для последующих операций."""

    # A16: проверка лимита
    if len(_uploaded_files) >= MAX_UPLOADED_FILES:
        raise HTTPException(503, "Сервер перегружен. Попробуйте позже.")

    # Валидация: только изображения
    allowed_types = {"image/png", "image/jpeg", "image/tiff", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            400,
            f"Неподдерживаемый тип файла: {file.content_type}. "
            f"Допустимые: {', '.join(sorted(allowed_types))}",
        )

    # Сохраняем во временный файл
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()  # Закрыть ДО передачи пути в PIL (Windows: PermissionError)
    except Exception:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise HTTPException(500, "Ошибка при сохранении файла")

    file_id = uuid.uuid4().hex
    _uploaded_files[file_id] = (Path(tmp.name), file.filename or "upload.png")
    logger.info("Загружен файл: %s → file_id=%s", file.filename, file_id)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "upload.png",
        size_bytes=len(content),
    )


@router.post("/process/preview")
async def preview_image(
    request: PreviewRequest,
    background_tasks: BackgroundTasks,
):
    """Предпросмотр обработки. Возвращает PNG-файл уменьшенного размера."""

    # Найти загруженный файл
    entry = _uploaded_files.get(request.file_id)
    if entry is None:
        raise HTTPException(404, f"Файл не найден: {request.file_id}")

    input_path, _ = entry

    # Собрать конфиг
    full_config = load_config()
    machine_cfg = full_config.get("processing", {}).get(request.machine, {})
    if request.params:
        machine_cfg = {**machine_cfg, **request.params}

    # CPU-bound: запуск в отдельном потоке
    try:
        result: PreviewResult = await asyncio.wait_for(
            asyncio.to_thread(
                process_preview,
                input_path=str(input_path),
                machine=request.machine,
                machine_cfg=machine_cfg,
            ),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            408,
            "Превышено время предпросмотра (15 сек). "
            "Попробуйте уменьшить размер изображения.",
        )
    except Exception as exc:
        logger.exception("Ошибка предпросмотра: %s", exc)
        raise HTTPException(500, f"Ошибка обработки: {exc}")

    # Сохранить результат во временный файл для отдачи
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_name = tmp.name
    tmp.close()

    try:
        result.image.save(tmp_name, format="PNG")
    except Exception as exc:
        Path(tmp_name).unlink(missing_ok=True)
        raise HTTPException(500, f"Ошибка сохранения результата: {exc}")

    # Удалить временный файл после отдачи
    background_tasks.add_task(lambda: Path(tmp_name).unlink(missing_ok=True))

    # Освободить память PipelineResult
    result.release_intermediates()

    headers = {
        "X-Diagnostics-Face-Brightness": str(result.diagnostics.get("face_brightness", "")),
        "X-Diagnostics-Glow-Value": str(result.diagnostics.get("glow_value", "")),
        "X-Diagnostics-Black-Ratio": str(result.diagnostics.get("black_ratio", "")),
        "X-Diagnostics-Warnings": "; ".join(result.diagnostics.get("warnings", [])),
    }

    return FileResponse(
        tmp_name,
        media_type="image/png",
        filename="preview.png",
        headers=headers,
        background=background_tasks,
    )


@router.post("/process/export")
async def export_image(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
):
    """Экспорт обработанного изображения в полном разрешении (TIFF/PNG)."""

    # Найти загруженный файл
    entry = _uploaded_files.get(request.file_id)
    if entry is None:
        raise HTTPException(404, f"Файл не найден: {request.file_id}")

    input_path, _ = entry

    # Собрать конфиг
    full_config = load_config()
    machine_cfg = full_config.get("processing", {}).get(request.machine, {})
    if request.params:
        machine_cfg = {**machine_cfg, **request.params}

    # CPU-bound: запуск в отдельном потоке
    fmt = request.format  # "tiff" или "png"
    suffix = ".tiff" if fmt == "tiff" else ".png"
    media_type = "image/tiff" if fmt == "tiff" else "image/png"

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                process_export,
                input_path=str(input_path),
                machine=request.machine,
                machine_cfg=machine_cfg,
                export_format=fmt,
            ),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            408,
            "Превышено время экспорта (60 сек). "
            "Попробуйте уменьшить размер изображения.",
        )
    except Exception as exc:
        logger.exception("Ошибка экспорта: %s", exc)
        raise HTTPException(500, f"Ошибка обработки: {exc}")

    # Сохранить результат во временный файл для отдачи
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_name = tmp.name
    tmp.close()

    try:
        result.image.save(tmp_name, format=fmt.upper())
    except Exception as exc:
        Path(tmp_name).unlink(missing_ok=True)
        raise HTTPException(500, f"Ошибка сохранения результата: {exc}")

    # Удалить временный файл после отдачи
    background_tasks.add_task(lambda: Path(tmp_name).unlink(missing_ok=True))

    # Освободить память PipelineResult
    result.release_intermediates()

    return FileResponse(
        tmp_name,
        media_type=media_type,
        filename=f"result{suffix}",
        background=background_tasks,
    )
```

**Ключевые решения**:

| Решение | Обоснование |
|---------|-------------|
| `asyncio.to_thread` | Pillow/numpy — CPU-bound, блокируют event loop. Без этого `/api/health` недоступен во время обработки |
| `asyncio.wait_for(timeout=15.0)` | Preview: 15 сек достаточно для 2048×2048. Если дольше — 408 + подсказка уменьшить изображение |
| `asyncio.wait_for(timeout=60.0)` | Export: полный TIFF занимает больше времени. 60 сек — безопасный лимит |
| `BackgroundTask` для `FileResponse` | Временный файл удаляется **после** отдачи клиенту, а не до |
| `tmp.close()` ДО `result.image.save()` | На Windows файл занят, пока не закрыт. `NamedTemporaryFile(delete=False)` + ручное закрытие |
| `MAX_UPLOADED_FILES = 50` | A16: защита от бесконтрольного роста `_uploaded_files`. При 50 файлах по 5 МБ = 250 МБ диска |
| `_ttl_cleanup()` фоновая корутина | Удаляет файлы старше 30 минут — нет утечки диска при долгой работе |
| Диагностика в `X-Diagnostics-*` заголовках | Не требует парсинга тела ответа (которое — бинарный PNG) |

---

### 4. Создать `routers/config.py` — управление конфигурацией (A3: deep_merge)

**Файл**: `retouch_ui/backend/routers/config.py`
**Обоснование**: Эндпоинты для чтения/записи конфигурации и получения дефолтов. **A3 CRITICAL**: `PUT /api/config` делает `deep_merge(DEFAULTS, request.config)` перед сохранением — это предотвращает потерю ключей, которые есть в DEFAULTS, но не были отправлены фронтендом.

```python
"""Роутер конфигурации: чтение, обновление, дефолты."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from retouch.config import (
    DEFAULTS,
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

    # Валидация объединённого конфига
    warnings = validate_config(full_config)

    # Определить путь сохранения
    config_path = find_config_path()
    if config_path is None:
        config_path = Path.cwd() / "config.yaml"

    # Сохранить
    try:
        with open(config_path, "w") as f:
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
```

**Ключевые решения**:

| Решение | Обоснование |
|---------|-------------|
| `deep_merge(DEFAULTS, request.config)` в PUT | A3: Если UI отправит только секцию `processing` без `vignette` — виньетка не потеряется. Если в yaml-файле добавлены ключи, которых нет в UI — они сохранятся через merge с DEFAULTS |
| `validate_config()` после merge | Валидируем итоговый конфиг, а не то, что прислал клиент |
| `find_config_path()` с fallback на CWD | Если config.yaml не найден — создаём в текущей директории |
| `yaml.dump(allow_unicode=True)` | Русские комментарии в yaml сохраняются корректно |

**Сценарий A3 — до и после исправления**:

```
# DEFAULTS содержит:
#   processing.laser.face_region_top: 0.45

# Фронтенд отправляет (без face_region_top):
#   { "processing": { "laser": { "brightness": 1.2 } } }

# БЕЗ deep_merge (v3.3 — БАГ):
#   config.yaml = { "processing": { "laser": { "brightness": 1.2 } } }
#   → face_region_top ПОТЕРЯН

# С deep_merge (v3.4 — ИСПРАВЛЕНО):
#   full_config = deep_merge(DEFAULTS, request.config)
#   → { "processing": { "laser": { "brightness": 1.2, "face_region_top": 0.45, ... } } }
#   → Все ключи из DEFAULTS сохранены
```

---

### 5. Создать `routers/presets.py` — управление пресетами (A11: find_config_path)

**Файл**: `retouch_ui/backend/routers/presets.py`
**Обоснование**: Пресеты — YAML-файлы в директории `presets/`. **A11**: `_presets_dir()` использует `find_config_path()` как якорь вместо хрупкой 4-уровневой навигации по `__file__`.

```python
"""Роутер пресетов: список, создание, удаление."""

from __future__ import annotations

import logging
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
    # Валидация имени — только безопасные символы
    safe_name = request.name.replace("/", "_").replace("\\", "_").replace("..", "_")
    if safe_name != request.name:
        raise HTTPException(400, f"Недопустимое имя пресета. Используйте: {safe_name}")

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
    # Санитизация имени
    safe_name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
    preset_path = _presets_dir() / f"{safe_name}.yaml"

    if not preset_path.exists():
        raise HTTPException(404, f"Пресет '{safe_name}' не найден")

    try:
        preset_path.unlink()
        logger.info("Пресет удалён: %s", preset_path)
    except Exception as exc:
        raise HTTPException(500, f"Ошибка удаления пресета: {exc}")

    return {"deleted": safe_name}
```

**Ключевые решения**:

| Решение | Обоснование |
|---------|-------------|
| `find_config_path()` как якорь (A11) | Вместо `Path(__file__).parent.parent.parent.parent / "presets"` — 4 уровня `__file__` ломаются при изменении структуры. `find_config_path()` уже знает, где корень проекта |
| Санитизация имени пресета | `../`, `/`, `\\` в имени — защита от path traversal |
| `yaml.safe_load()` | Только безопасная загрузка YAML — нет выполнения произвольного кода |
| 409 Conflict при дубликате | Явная ошибка вместо молчной перезаписи |

---

### 6. Создать `main.py` — FastAPI приложение

**Файл**: `retouch_ui/backend/main.py`
**Обоснование**: Точка входа бэкенда. Lifespan запускает TTL-очистку загруженных файлов. CORS разрешает все источники (локальный инструмент, один оператор). Health-эндпоинт показывает версию.

```python
"""FastAPI-бэкенд granite-retouch Web UI.

Запуск: uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8001 --reload
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from retouch import __version__

from .routers import config, presets, process
from .schemas import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("retouch_ui")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup: запустить TTL-очистку загруженных файлов
    cleanup_task = asyncio.create_task(process._ttl_cleanup())
    logger.info("granite-retouch backend v%s запущен", __version__)
    yield
    # Shutdown: отменить фоновые задачи
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("granite-retouch backend остановлен")


app = FastAPI(
    title="granite-retouch API",
    version=__version__,
    lifespan=lifespan,
)

# CORS — локальный инструмент, один оператор
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(process.router)
app.include_router(config.router)
app.include_router(presets.router)


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Проверка доступности бэкенда."""
    return HealthResponse(status="ok", version=__version__)
```

**Ключевые решения**:

| Решение | Обоснование |
|---------|-------------|
| `lifespan` вместо `on_event` | `on_event` устарел в FastAPI ≥ 0.100. `lifespan` — рекомендуемый способ |
| TTL-cleanup в lifespan | Фоновая корутина запускается при старте, отменяется при shutdown |
| CORS `allow_origins=["*"]` | Локальный инструмент; строгий CORS создаёт проблемы на нестандартных портах |
| `/api/health` с версией | Мониторинг + информация о версии бэкенда в одном запросе |
| `--reload` в dev-режиме | Автоматическая перезагрузка при изменении кода |

---

### 7. Создать `requirements.txt` для бэкенда

**Файл**: `retouch_ui/backend/requirements.txt`

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
python-multipart>=0.0.9
pyyaml>=6.0
pydantic>=2.0
```

**Обоснование**:
- `fastapi` — веб-фреймворк
- `uvicorn[standard]` — ASGI-сервер с uvloop и watchfiles (--reload)
- `python-multipart` — необходим для `UploadFile` в FastAPI
- `pyyaml` — чтение/запись config.yaml и пресетов
- `pydantic>=2.0` — модели запросов/ответов (зависимость FastAPI, указана явно)

> **Примечание**: Основной пакет `granite-retouch` устанавливается отдельно через `pip install -e .`. `requirements.txt` здесь — только для `retouch_ui/backend/`.

---

### 8. Команда запуска бэкенда

**Добавить в Makefile** (корень проекта):

```makefile
# ─── Web UI ────────────────────────────────────────────────────────

.PHONY: ui-backend
ui-backend: ## Запустить FastAPI backend (dev-режим)
	cd retouch_ui/backend && \
	uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8001 --reload

.PHONY: ui
ui: ## Запустить backend + frontend (два процесса)
	@echo "Запуск backend (port 8001) и frontend (port 5173)..."
	$(MAKE) ui-backend & $(MAKE) ui-frontend & wait
```

> Полные цели `ui`, `ui-frontend`, `ui-prod` определяются в Фазе 2.

---

### 9. Обновить `.gitignore`

**Файл**: `.gitignore` (корень проекта)

Добавить в конец:

```gitignore
# Web UI — временные файлы
retouch_ui/frontend/node_modules/
retouch_ui/frontend/dist/
retouch_ui/frontend/.vite/

# Временные файлы загрузок (если backend запускался локально)
/tmp_upload_*
```

---

### 10. Обновить BACKLOG.md (A8)

Отметить задачи, которые закрывает Фаза 1:

```markdown
### BACKLOG-001: Web UI для настройки обработки портретов
**Статус**: In Progress — FastAPI backend реализован (Фаза 1), frontend — Фаза 2
```

---

## Порядок выполнения

```
1. Задача 1  — __init__.py (A13)                                    ~5 мин
2. Задача 2  — schemas.py                                           ~30 мин
3. Задача 7  — requirements.txt                                     ~5 мин
4. Задача 6  — main.py (можно без роутеров — проверить /api/health) ~30 мин
5. Задача 3  — routers/process.py                                   ~90 мин
6. Задача 4  — routers/config.py (с deep_merge — A3)                ~30 мин
7. Задача 5  — routers/presets.py (с find_config_path — A11)        ~30 мин
8. Задача 8  — Makefile (ui-backend)                                ~10 мин
9. Задача 9  — .gitignore                                           ~5 мин
10. Задача 10 — обновить BACKLOG.md                                 ~5 мин
11. Ручное тестирование всех эндпоинтов                             ~30 мин
12. git tag phase1-done
```

**Итого**: ~4.5 часа чистого времени (6–8 часов с отладкой и непредвиденными ситуациями)

---

## Ручное тестирование (после реализации)

### 1. Запуск бэкенда

```bash
cd /path/to/granite-retouch
pip install -e .
cd retouch_ui/backend
pip install -r requirements.txt
uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8001
```

Ожидание: `INFO: Uvicorn running on http://127.0.0.1:8001`

### 2. Health-чек

```bash
curl http://127.0.0.1:8001/api/health
```

Ожидание: `{"status":"ok","version":"3.0.0-dev"}`

### 3. Получить конфигурацию

```bash
curl http://127.0.0.1:8001/api/config
```

Ожидание: JSON с ключами `config` и `warnings`.

### 4. Получить дефолты

```bash
curl http://127.0.0.1:8001/api/config/defaults
```

Ожидание: JSON с ключом `defaults`, содержащий DEFAULTS.

### 5. Обновить конфигурацию (проверка A3 — deep_merge)

```bash
# Отправляем ЧАСТИЧНЫЙ конфиг — только brightness
curl -X PUT http://127.0.0.1:8001/api/config \
  -H "Content-Type: application/json" \
  -d '{"config": {"processing": {"laser": {"brightness": 1.5}}}}'
```

Ожидание:
- `saved: true`
- В config.yaml сохранён **полный** конфиг с `face_region_top`, `highlight_start` и остальными ключами из DEFAULTS
- `brightness` = 1.5 (из запроса), `face_region_top` = 0.45 (из DEFAULTS)

Проверка: `cat config.yaml` — содержит `face_region_top: 0.45` и `brightness: 1.5`.

### 6. Загрузить изображение

```bash
curl -X POST http://127.0.0.1:8001/api/upload \
  -F "file=@/path/to/test-image.png"
```

Ожидание: `{"file_id":"<uuid>","filename":"test-image.png","size_bytes":<N>}`

### 7. Предпросмотр

```bash
curl -X POST http://127.0.0.1:8001/api/process/preview \
  -H "Content-Type: application/json" \
  -d '{"file_id":"<uuid>","machine":"laser"}' \
  -o preview.png
```

Ожидание: Файл `preview.png` — корректный PNG. Заголовки `X-Diagnostics-*` содержат значения.

### 8. Экспорт

```bash
curl -X POST http://127.0.0.1:8001/api/process/export \
  -H "Content-Type: application/json" \
  -d '{"file_id":"<uuid>","machine":"laser","format":"tiff"}' \
  -o result.tiff
```

Ожидание: Файл `result.tiff` — корректный TIFF.

### 9. Пресеты (проверка A11 — find_config_path)

```bash
# Создать пресет
curl -X POST http://127.0.0.1:8001/api/presets \
  -H "Content-Type: application/json" \
  -d '{"name":"test-preset","config":{"processing":{"laser":{"brightness":1.3}}}}'

# Список пресетов
curl http://127.0.0.1:8001/api/presets

# Удалить пресет
curl -X DELETE http://127.0.0.1:8001/api/presets/test-preset
```

Ожидание: Пресет сохраняется в `presets/test-preset.yaml` (относительно корня проекта, определённого через `find_config_path()`).

### 10. Проверка лимита загрузок (A16)

```bash
# Загрузить 50 файлов, затем попытаться загрузить 51-й
# Ожидание: HTTP 503 "Сервер перегружен. Попробуйте позже."
```

### 11. Проверка `/api/health` во время обработки

В одном терминале:
```bash
# Загрузить большое изображение и запустить экспорт
curl -X POST http://127.0.0.1:8001/api/process/export \
  -H "Content-Type: application/json" \
  -d '{"file_id":"<uuid>","machine":"laser","format":"tiff"}' -o result.tiff
```

В другом терминале:
```bash
curl http://127.0.0.1:8001/api/health
```

Ожидание: `/api/health` отвечает мгновенно, не блокируется обработкой.

### 12. OpenAPI-документация

Открыть в браузере: `http://127.0.0.1:8001/docs`

Ожидание: Swagger UI со всеми эндпоинтами и моделями.

---

## Чеклист приёмки

- [ ] `python -c "from retouch_ui.backend.main import app"` — импорт без ошибок
- [ ] `python -c "from retouch_ui.backend.schemas import HealthResponse"` — Pydantic-модели доступны
- [ ] `__init__.py` существуют в `retouch_ui/`, `retouch_ui/backend/`, `retouch_ui/backend/routers/` (A13)
- [ ] `uvicorn retouch_ui.backend.main:app --port 8001` запускается без ошибок
- [ ] `GET /api/health` возвращает `{"status":"ok","version":"3.0.0-dev"}`
- [ ] `GET /api/config` возвращает конфиг с ключами `config` и `warnings`
- [ ] `GET /api/config/defaults` возвращает DEFAULTS
- [ ] `PUT /api/config` с частичным конфигом не теряет ключи из DEFAULTS (A3)
- [ ] После `PUT /api/config` — config.yaml содержит полный конфиг (deep_merge)
- [ ] `POST /api/upload` принимает PNG/JPEG/TIFF и возвращает file_id
- [ ] `POST /api/upload` с 51-м файлом возвращает 503 (A16: MAX_UPLOADED_FILES)
- [ ] `POST /api/process/preview` возвращает PNG с заголовками X-Diagnostics-*
- [ ] `POST /api/process/export` возвращает TIFF/PNG в полном разрешении
- [ ] `/api/health` доступен во время обработки изображения (asyncio.to_thread)
- [ ] Временные файлы удаляются после отдачи (BackgroundTask)
- [ ] TTL-очистка удаляет файлы старше 30 минут
- [ ] `POST /api/presets` создаёт YAML-файл в `presets/` (A11: через find_config_path)
- [ ] `DELETE /api/presets/{name}` удаляет YAML-файл
- [ ] Path traversal в имени пресета блокируется (sanitization)
- [ ] `GET /api/presets` возвращает список пресетов
- [ ] `/docs` (Swagger UI) доступен и показывает все эндпоинты
- [ ] BACKLOG.md обновлён — BACKLOG-001 статус In Progress (A8)
- [ ] Git-тег `phase1-done` создан
