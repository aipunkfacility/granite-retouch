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
        ├── main.py              # FastAPI app + startup/shutdown
        ├── routers/
        │   ├── process.py       # POST /process/preview, /process/export
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
```

Существующие зависимости (уже установлены): Pillow, PyYAML, numpy, scipy, pydantic.

---

## Задача 1: schemas.py — модели запросов и ответов

```python
"""Pydantic модели для FastAPI API granite-retouch."""
from pydantic import BaseModel, Field
from typing import Optional


# === Запросы ===

class PreviewRequest(BaseModel):
    machine_type: str = Field("laser", pattern="^(laser|impact)$")
    config: Optional[dict] = None


class ExportRequest(BaseModel):
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
```

---

## Задача 2: main.py — FastAPI приложение

```python
"""FastAPI backend для granite-retouch Web UI."""
import logging
from pathlib import Path
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
    logger.info("retouch-ui backend shutting down")


app = FastAPI(
    title="granite-retouch API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — только localhost для локального инструмента
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Vite default
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(process.router, prefix="/api", tags=["process"])
app.include_router(config.router, prefix="/api", tags=["config"])
app.include_router(presets.router, prefix="/api", tags=["presets"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Примечание по безопасности**: CORS ограничен localhost. Если кто-то запустит `uvicorn --host 0.0.0.0`, API станет доступен извне, но без аутентификации. Добавить предупреждение в README.

---

## Задача 3: routers/process.py — обработка изображений

```python
"""Роутер обработки изображений: предпросмотр и экспорт."""
import io
import base64
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from PIL import Image

import retouch.processing as proc
from retouch.config import load_config, deep_merge, DEFAULTS
from ..schemas import PreviewResponse, DiagnosticsResponse

logger = logging.getLogger("retouch-ui.process")
router = APIRouter()

# Кэш последнего preview (простой, in-memory)
_last_preview: dict | None = None
_last_preview_key: str = ""


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


@router.post("/process/preview", response_model=PreviewResponse)
async def process_preview(
    file: UploadFile = File(...),
    machine_type: str = Form("laser"),
    config_json: str | None = Form(None),
):
    """Обработка изображения для предпросмотра (уменьшенная копия).

    Возвращает base64-изображения каждого шага + диагностику.
    """
    import json

    # Валидация файла
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Файл должен быть изображением")

    # Читаем изображение
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:  # 20 MB лимит
        raise HTTPException(400, "Файл слишком большой (макс. 20 МБ)")

    # Сохраняем во временный файл (process_preview требует путь)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        config_override = json.loads(config_json) if config_json else None
        config = _get_config(config_override)

        result = proc.process_preview(
            input_path=tmp_path,
            machine_type=machine_type,
            config=config,
            max_size=768,
        )

        # Формируем ответ
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

        # Кэшируем
        global _last_preview, _last_preview_key
        _last_preview_key = f"{tmp_path}:{machine_type}:{config_json}"
        _last_preview = {"images": images, "diagnostics": diagnostics}

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
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/process/export")
async def process_export(
    file: UploadFile = File(...),
    machine_type: str = Form("laser"),
    config_json: str | None = Form(None),
    format: str = Form("tiff"),
):
    """Полная обработка + скачивание файла."""
    import json
    from fastapi.responses import FileResponse

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "Файл слишком большой (макс. 20 МБ)")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_in:
        tmp_in.write(contents)
        tmp_in_path = tmp_in.name

    suffix = ".tif" if format == "tiff" else ".png"
    tmp_out = tempfile.mktemp(suffix=suffix)

    try:
        config_override = json.loads(config_json) if config_json else None
        config = _get_config(config_override)

        proc.process_export(
            input_path=tmp_in_path,
            output_path=tmp_out,
            machine_type=machine_type,
            config=config,
        )

        media_type = "image/tiff" if format == "tiff" else "image/png"
        filename = f"retouch_result{suffix}"

        return FileResponse(
            path=tmp_out,
            media_type=media_type,
            filename=filename,
        )

    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.exception("Export processing failed")
        raise HTTPException(500, f"Ошибка экспорта: {e}")
```

**Важно**: Временные файлы удаляются в `finally` для preview. Для export — `FileResponse` удалит файл после отдачи (параметр `background`), но это нужно проверить. Если нет — добавить cleanup.

---

## Задача 4: routers/config.py — управление конфигурацией

```python
"""Роутер конфигурации: чтение, запись, дефолты."""
import yaml
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from retouch.config import load_config, validate_config, DEFAULTS
from ..schemas import ConfigResponse, ConfigUpdateResponse, ConfigUpdateRequest

logger = logging.getLogger("retouch-ui.config")
router = APIRouter()


def _find_config_path() -> Path | None:
    """Найти config.yaml."""
    candidates = [
        Path(__file__).parent.parent.parent.parent / "config.yaml",  # проект
        Path.cwd() / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Текущий конфиг (из config.yaml или DEFAULTS)."""
    config_path = _find_config_path()
    source = str(config_path) if config_path else "defaults"
    config = load_config()
    warnings = validate_config(config)
    return ConfigResponse(config=config, source=source, warnings=warnings)


@router.put("/config", response_model=ConfigUpdateResponse)
async def update_config(request: ConfigUpdateRequest):
    """Сохранить конфиг в config.yaml."""
    warnings = validate_config(request.config)

    config_path = _find_config_path()
    if config_path is None:
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

---

## Задача 5: routers/presets.py — пресеты

```python
"""Роутер пресетов: сохранение/загрузка наборов параметров."""
import yaml
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import PresetsListResponse, PresetItem, PresetCreateRequest

logger = logging.getLogger("retouch-ui.presets")
router = APIRouter()


def _presets_dir() -> Path:
    """Директория с пресетами."""
    d = Path(__file__).parent.parent.parent.parent / "presets"
    d.mkdir(exist_ok=True)
    return d


@router.get("/presets", response_model=PresetsListResponse)
async def list_presets():
    """Список доступных пресетов."""
    presets = []
    for f in sorted(_presets_dir().glob("*.yaml")):
        with open(f) as fh:
            cfg = yaml.safe_load(fh) or {}
        presets.append(PresetItem(name=f.stem, config=cfg))
    return PresetsListResponse(presets=presets)


@router.post("/presets")
async def create_preset(request: PresetCreateRequest):
    """Сохранить конфиг как пресет."""
    path = _presets_dir() / f"{request.name}.yaml"
    if path.exists():
        raise HTTPException(409, f"Пресет '{request.name}' уже существует")
    with open(path, "w") as f:
        yaml.dump(request.config, f, default_flow_style=False, allow_unicode=True)
    return {"created": True, "name": request.name}


@router.delete("/presets/{name}")
async def delete_preset(name: str):
    """Удалить пресет."""
    path = _presets_dir() / f"{name}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Пресет '{name}' не найден")
    path.unlink()
    return {"deleted": True, "name": name}
```

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
- [ ] `GET /api/health` возвращает `{"status": "ok"}`
- [ ] `POST /api/process/preview` принимает PNG и возвращает base64 + диагностику
- [ ] `POST /api/process/export` отдаёт TIFF/PNG файл
- [ ] `GET /api/config` возвращает текущий конфиг
- [ ] `PUT /api/config` сохраняет config.yaml
- [ ] `GET /api/config/defaults` возвращает DEFAULTS
- [ ] `GET /api/presets` возвращает список пресетов
- [ ] `POST /api/presets` создаёт пресет
- [ ] `DELETE /api/presets/{name}` удаляет пресет
- [ ] CORS работает для localhost:5173 (Vite)
- [ ] RAM при простое ≤ 150 МБ
- [ ] RAM при обработке 2048×2048 ≤ 600 МБ
