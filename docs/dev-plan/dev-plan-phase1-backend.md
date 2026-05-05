# Фаза 1: FastAPI Backend

**Предыдущий этап**: [Фаза 0](dev-plan-phase0-pipeline.md)
**Следующий этап**: [Фаза 2](dev-plan-phase2-frontend.md) (можно параллелить)
**Время**: 6–8 часов
**Цель**: HTTP-API для обработки изображений, доступное из браузера.

---

## Директория

```
granite-retouch/
└── retouch-ui/
    └── backend/
        ├── main.py              # FastAPI app + asyncio.to_thread + version в health
        ├── routers/
        │   ├── process.py       # POST /upload, /process/preview (по file_id), /process/export
        │   ├── config.py        # GET/PUT /config, /config/defaults
        │   └── presets.py       # GET/POST/DELETE /presets
        ├── schemas.py           # Pydantic модели для API
        └── requirements.txt     # fastapi, uvicorn, python-multipart
```

---

## Зависимости

**`retouch-ui/backend/requirements.txt`**:
```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
python-multipart>=0.0.9
pydantic>=2.0
```

**`pyproject.toml`** — optional dependency:
```toml
[project.optional-dependencies]
webui = ["pydantic>=2.0", "fastapi>=0.110.0", "uvicorn[standard]>=0.29.0", "python-multipart>=0.0.9"]
```

---

## Задача 1: schemas.py — модели запросов и ответов

```python
"""Pydantic модели для FastAPI API granite-retouch."""
from pydantic import BaseModel, Field
from typing import Optional


# === Запросы ===

class PreviewRequest(BaseModel):
    file_id: str = Field(..., min_length=1)
    machine_type: str = Field("laser", pattern="^(laser|impact)$")
    config: Optional[dict] = None


class ExportRequest(BaseModel):
    file_id: str = Field(..., min_length=1)
    machine_type: str = Field("laser", pattern="^(laser|impact)$")
    config: Optional[dict] = None
    format: str = Field("tiff", pattern="^(tiff|png)$")


class ConfigUpdateRequest(BaseModel):
    config: dict


class PresetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    config: dict


# === Ответы ===

class DiagnosticsResponse(BaseModel):
    glow_size: int
    glow_opacity: float
    face_brightness_before: float
    face_brightness_after: float
    face_correction_factor: float
    black_ratio: float
    blue_ratio: float
    width: int
    height: int


class PreviewResponse(BaseModel):
    images: dict[str, str]          # ключ: step, значение: base64 data URI
    diagnostics: DiagnosticsResponse
    warnings: list[str]


class UploadResponse(BaseModel):
    file_id: str


class ConfigResponse(BaseModel):
    config: dict
    source: str                     # "config.yaml" | "defaults"
    warnings: list[str]


class ConfigUpdateResponse(BaseModel):
    saved: bool
    path: str
    warnings: list[str]


class PresetItem(BaseModel):
    name: str
    config: dict


class PresetsListResponse(BaseModel):
    presets: list[PresetItem]


class HealthResponse(BaseModel):
    status: str
    version: str
```

---

## Задача 2: main.py — FastAPI приложение

```python
"""FastAPI backend для granite-retouch Web UI."""
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import process, config, presets

logger = logging.getLogger("retouch-ui")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown."""
    logger.info("retouch-ui backend starting on :8001")
    yield
    # Cleanup: удалить загруженные файлы
    from .routers.process import _cleanup_all_files
    _cleanup_all_files()
    logger.info("retouch-ui backend shutting down")


app = FastAPI(
    title="granite-retouch API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — для локального инструмента разрешаем все origins
# Если сервис доступен извне — ограничить до localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(process.router, prefix="/api", tags=["process"])
app.include_router(config.router, prefix="/api", tags=["config"])
app.include_router(presets.router, prefix="/api", tags=["presets"])


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check с версией — полезно для отладки."""
    import retouch
    return {"status": "ok", "version": retouch.__version__}
```

---

## Задача 3: routers/process.py — обработка с file_id + asyncio.to_thread + BackgroundTask

```python
"""Роутер обработки изображений: загрузка, предпросмотр, экспорт."""
import io
import uuid
import time
import base64
import logging
import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image

import retouch.processing as proc
from retouch.config import load_config, deep_merge, validate_config
from ..schemas import PreviewResponse, DiagnosticsResponse, UploadResponse

logger = logging.getLogger("retouch-ui.process")
router = APIRouter()

# In-memory хранилище загруженных файлов: id → (path, metadata)
_uploaded_files: dict[str, tuple[str, dict]] = {}

# TTL-очистка: 30 минут
_CLEANUP_INTERVAL = 1800


def _image_to_base64(img: Image.Image, format: str = "PNG") -> str:
    """Конвертировать PIL Image в base64 data URI."""
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/{format.lower()};base64,{b64}"


def _get_config(config_override: dict | None) -> dict:
    """Получить конфиг: base + override через deep_merge."""
    base = load_config()
    if config_override:
        return deep_merge(base, config_override)
    return base


def _cleanup_expired_files():
    """Удалить устаревшие загруженные файлы (TTL)."""
    now = time.time()
    to_delete = [
        fid for fid, (path, meta) in _uploaded_files.items()
        if now - meta.get("uploaded_at", 0) > _CLEANUP_INTERVAL
    ]
    for fid in to_delete:
        Path(_uploaded_files[fid][0]).unlink(missing_ok=True)
        del _uploaded_files[fid]
    if to_delete:
        logger.info("Cleaned up %d expired uploaded files", len(to_delete))


def _cleanup_all_files():
    """Удалить все загруженные файлы (при shutdown)."""
    for fid, (path, meta) in list(_uploaded_files.items()):
        Path(path).unlink(missing_ok=True)
    _uploaded_files.clear()


# === Загрузка изображения ===

@router.post("/process/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Загрузить изображение, получить file_id для последующих запросов.

    Файл загружается один раз. Дальше preview/export используют file_id.
    Это позволяет не пересылать 5-20 МБ при каждом движении слайдера.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Файл должен быть изображением")

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:  # 20 MB лимит
        raise HTTPException(400, "Файл слишком большой (макс. 20 МБ)")

    file_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(contents)
        _uploaded_files[file_id] = (tmp.name, {
            "original_name": file.filename,
            "size": len(contents),
            "uploaded_at": time.time(),  # ← ОБЯЗАТЕЛЬНО для TTL
        })

    # Периодическая очистка
    _cleanup_expired_files()

    return UploadResponse(file_id=file_id)


# === Предпросмотр ===

@router.post("/process/preview", response_model=PreviewResponse)
async def process_preview(
    file_id: str = Form(None),
    file: UploadFile = File(None),       # fallback: прямая загрузка
    machine_type: str = Form("laser"),
    config_json: str | None = Form(None),
):
    """Обработка изображения для предпросмотра (уменьшенная копия).

    Рекомендуемый способ: загрузить через /process/upload, затем передать file_id.
    Fallback: передать файл напрямую (для совместимости).
    """
    import json

    # Определяем путь к файлу
    tmp_path_cleanup = None
    if file_id and file_id in _uploaded_files:
        tmp_path = _uploaded_files[file_id][0]
    elif file:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
            tmp_path_cleanup = tmp_path
    else:
        raise HTTPException(400, "Нужен file_id или файл")

    try:
        config_override = json.loads(config_json) if config_json else None
        config = _get_config(config_override)

        # asyncio.to_thread — не блокировать event loop
        result = await asyncio.to_thread(
            proc.process_preview,
            input_path=tmp_path,
            machine_type=machine_type,
            config=config,
            max_size=768,
        )

        images = {
            "chromakey": _image_to_base64(result.img_chromakey),
            "glow": _image_to_base64(result.img_glow),
            "leveled": _image_to_base64(result.img_leveled),
            "face_corrected": _image_to_base64(result.img_face_corrected),
            "final": _image_to_base64(result.img_final),
            "arch_mask": _image_to_base64(result.arch_mask),
        }

        diagnostics = DiagnosticsResponse(
            glow_size=result.glow_size,
            glow_opacity=result.glow_opacity,
            face_brightness_before=result.face_brightness_before,
            face_brightness_after=result.face_brightness_after,
            face_correction_factor=result.face_correction_factor,
            black_ratio=result.black_ratio,
            blue_ratio=result.blue_ratio,
            width=result.width,
            height=result.height,
        )

        return PreviewResponse(
            images=images,
            diagnostics=diagnostics,
            warnings=result.warnings,
        )

    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.exception("Preview processing failed")
        raise HTTPException(500, f"Ошибка обработки: {e}")
    finally:
        # Удаляем временный файл только если это fallback-загрузка
        if tmp_path_cleanup:
            Path(tmp_path_cleanup).unlink(missing_ok=True)


# === Экспорт ===

@router.post("/process/export")
async def process_export(
    file_id: str = Form(None),
    file: UploadFile = File(None),
    machine_type: str = Form("laser"),
    config_json: str | None = Form(None),
    format: str = Form("tiff"),
):
    """Полная обработка + скачивание файла."""
    import json

    # Определяем путь
    tmp_in_cleanup = None
    if file_id and file_id in _uploaded_files:
        tmp_in_path = _uploaded_files[file_id][0]
    elif file:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(contents)
            tmp_in_path = tmp.name
            tmp_in_cleanup = tmp_in_path
    else:
        raise HTTPException(400, "Нужен file_id или файл")

    suffix = ".tif" if format == "tiff" else ".png"
    tmp_out = tempfile.mktemp(suffix=suffix)

    try:
        config_override = json.loads(config_json) if config_json else None
        config = _get_config(config_override)

        # asyncio.to_thread для тяжёлой обработки
        await asyncio.to_thread(
            proc.process_export,
            input_path=tmp_in_path,
            output_path=tmp_out,
            machine_type=machine_type,
            config=config,
        )

        media_type = "image/tiff" if format == "tiff" else "image/png"
        filename = f"retouch_result{suffix}"

        # BackgroundTask для удаления временного выходного файла после отдачи
        return FileResponse(
            path=tmp_out,
            media_type=media_type,
            filename=filename,
            background=BackgroundTasks().add_task(
                lambda p=tmp_out: Path(p).unlink(missing_ok=True)
            ),
        )

    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.exception("Export processing failed")
        Path(tmp_out).unlink(missing_ok=True)
        raise HTTPException(500, f"Ошибка экспорта: {e}")
    finally:
        if tmp_in_cleanup:
            Path(tmp_in_cleanup).unlink(missing_ok=True)
```

**Ключевые отличия от v3.0:**
- **file_id** — загрузка один раз, preview/export по ID (перенесено из Фазы 3)
- **asyncio.to_thread** — CPU-bound обработка не блокирует event loop
- **BackgroundTask** для FileResponse — временный файл удаляется после отдачи
- **`uploaded_at: time.time()`** — TTL-очистка реально работает
- **CORS `allow_origins=["*"]`** — для локального инструмента
- Нет мёртвого кэша — убран `_last_preview` / `_last_preview_key`

---

## Задача 4: routers/config.py — через retouch.config

```python
"""Роутер конфигурации: чтение, запись, дефолты."""
import yaml
import logging

from fastapi import APIRouter, HTTPException

from retouch.config import load_config, validate_config, DEFAULTS, find_config_path
from ..schemas import ConfigResponse, ConfigUpdateResponse, ConfigUpdateRequest

logger = logging.getLogger("retouch-ui.config")
router = APIRouter()


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Текущий конфиг (из config.yaml или DEFAULTS)."""
    config_path = find_config_path()
    source = str(config_path) if config_path else "defaults"
    config = load_config()
    warnings = validate_config(config)
    return ConfigResponse(config=config, source=source, warnings=warnings)


@router.put("/config", response_model=ConfigUpdateResponse)
async def update_config(request: ConfigUpdateRequest):
    """Сохранить конфиг в config.yaml."""
    warnings = validate_config(request.config)

    config_path = find_config_path()
    if config_path is None:
        from pathlib import Path
        config_path = Path.cwd() / "config.yaml"

    with open(config_path, "w") as f:
        yaml.dump(request.config, f, default_flow_style=False, allow_unicode=True)

    logger.info(f"Config saved to {config_path}")
    return ConfigUpdateResponse(saved=True, path=str(config_path), warnings=warnings)


@router.get("/config/defaults")
async def get_defaults():
    """Дефолтные значения конфига."""
    return {"config": DEFAULTS, "warnings": validate_config(DEFAULTS)}
```

**Ключевое изменение**: поиск `config.yaml` делегирован функции `find_config_path()` из `retouch/config.py` — один источник истины.

Добавить в `retouch/config.py`:
```python
def find_config_path() -> Path | None:
    """Найти config.yaml. Единая точка поиска для CLI и backend."""
    candidates = [
        Path(__file__).parent.parent / "config.yaml",
        Path.cwd() / "config.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
```

---

## Задача 5: routers/presets.py

Без изменений — см. v3.0.

---

## Задача 6: Запуск

**Команда**:
```bash
cd retouch-ui/backend
uvicorn main:app --port 8001 --reload --workers 1
```

`--workers 1` — **критично при 4 ГБ**. Каждый worker загружает Pillow + numpy.

**Makefile** (добавить в корневой Makefile):
```makefile
ui-backend:      ## Запустить FastAPI backend
	cd retouch-ui/backend && uvicorn main:app --port 8001 --reload --workers 1
```

---

## Чеклист приёмки

- [ ] `uvicorn main:app --port 8001` запускается без ошибок
- [ ] `GET /api/health` возвращает `{"status": "ok", "version": "2.6.0"}`
- [ ] `POST /api/process/upload` принимает PNG и возвращает file_id
- [ ] `POST /api/process/preview` по file_id возвращает base64 + диагностику
- [ ] `POST /api/process/preview` по file (fallback) работает
- [ ] `POST /api/process/export` отдаёт TIFF/PNG файл
- [ ] Временные файлы экспорта удаляются после отдачи (BackgroundTask)
- [ ] `/api/health` доступен во время обработки изображения (asyncio.to_thread)
- [ ] `GET /api/config` возвращает текущий конфиг
- [ ] `PUT /api/config` сохраняет config.yaml
- [ ] `GET /api/config/defaults` возвращает DEFAULTS
- [ ] Поиск config.yaml делегирован `retouch.config.find_config_path`
- [ ] CORS разрешает запросы с любого origin
- [ ] RAM при простое ≤ 150 МБ
- [ ] RAM при обработке 2048×2048 ≤ 600 МБ
- [ ] TTL-очистка загруженных файлов работает (uploaded_at установлен)
