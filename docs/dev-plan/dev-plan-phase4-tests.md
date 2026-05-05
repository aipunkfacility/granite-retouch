# Фаза 4: Тесты

**Предыдущий этап**: [Фаза 3](dev-plan-phase3-integration.md)
**Время**: 3–4 часа
**Цель**: Покрыть backend API и критические сценарии. Не стремиться к 100% — покрыть важнейшие пути.

---

## ⚠ Зависимость от Фазы 0

Тесты в этом файле предполагают, что Фаза 0 завершена:
- `process_steps()`, `process_preview()`, `process_export()` доступны
- `PipelineResult` существует
- `check_face_brightness()` возвращает кортеж
- `deep_merge()`, `validate_config()` доступны из `retouch.config`
- `find_config_path()` доступен из `retouch.config`

Если Фаза 0 не завершена — эти тесты не скомпилируются.

---

## ⚠ Совместимость asyncio.to_thread + TestClient

Роутеры используют `asyncio.to_thread()` для CPU-bound операций. `TestClient` — синхронный WSGI-клиент, который создаёт event loop внутри `anyio`. На практике `asyncio.to_thread` работает корректно с `TestClient`, но если тесты запускаются с `pytest-asyncio` в режиме `asyncio_mode = "auto"`, возможны конфликты вложенных event loops.

**Рекомендация**: при первом запуске тестов проверить совместимость. Если возникают ошибки `RuntimeError: This event loop is already running`, добавить в `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "strict"
```

---

## Принцип тестирования

- **Backend**: pytest + FastAPI TestClient (синхронный, без uvicorn)
- **Frontend**: ручное тестирование (Playwright не нужен для локального инструмента)
- **Синтетические изображения**: как в существующих тестах — быстрое создание через PIL
- **Изоляция**: тесты config/presets не пишут в реальные файлы проекта

---

## Задача 1: Backend API тесты

**Директория**: `retouch-ui/backend/tests/`

### conftest.py

```python
"""Общие фикстуры для тестов backend API."""
import tempfile
from pathlib import Path

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from ..main import app


@pytest.fixture
def client():
    """FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def sample_chromakey_png():
    """Синтетическое изображение с синим хромакеем — как PNG bytes."""
    img = Image.new("RGBA", (512, 512), (0, 0, 255, 255))  # синий фон
    for x in range(200, 312):
        for y in range(200, 312):
            img.putpixel((x, y), (255, 255, 255, 255))  # белый субъект

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@pytest.fixture
def uploaded_file_id(client, sample_chromakey_png):
    """Загруженный файл через /api/process/upload — возвращает file_id."""
    res = client.post(
        "/api/process/upload",
        files={"file": ("test.png", sample_chromakey_png, "image/png")},
    )
    assert res.status_code == 200
    return res.json()["file_id"]
```

### test_process.py

```python
"""Тесты роутера обработки изображений."""
import json


def test_health_with_version(client):
    """GET /api/health возвращает ok + версию."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_upload_image(client, sample_chromakey_png):
    """POST /api/process/upload возвращает file_id."""
    res = client.post(
        "/api/process/upload",
        files={"file": ("test.png", sample_chromakey_png, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "file_id" in data
    assert len(data["file_id"]) > 0


def test_upload_invalid_file(client):
    """Загрузка не-изображения → 400."""
    res = client.post(
        "/api/process/upload",
        files={"file": ("test.txt", b"not an image", "text/plain")},
    )
    assert res.status_code == 400


def test_preview_by_file_id(client, uploaded_file_id):
    """POST /api/process/preview по file_id возвращает base64 + диагностику."""
    res = client.post(
        "/api/process/preview",
        data={"file_id": uploaded_file_id, "machine_type": "laser"},
    )
    assert res.status_code == 200
    data = res.json()

    assert "images" in data
    assert "diagnostics" in data
    assert "warnings" in data

    for step in ("chromakey", "glow", "leveled", "face_corrected", "final", "arch_mask"):
        assert step in data["images"]
        assert data["images"][step].startswith("data:image/png;base64,")

    diag = data["diagnostics"]
    assert "glow_size" in diag
    assert "face_brightness_before" in diag
    assert "face_brightness_after" in diag


def test_preview_laser_vs_impact(client, uploaded_file_id):
    """Laser и impact дают разный glow_size."""
    results = {}
    for machine in ("laser", "impact"):
        res = client.post(
            "/api/process/preview",
            data={"file_id": uploaded_file_id, "machine_type": machine},
        )
        results[machine] = res.json()["diagnostics"]["glow_size"]

    assert results["laser"] != results["impact"]


def test_preview_custom_config(client, uploaded_file_id):
    """Переопределение параметров через config_json."""
    custom_config = {"processing": {"laser": {"brightness": 1.40}}}
    res = client.post(
        "/api/process/preview",
        data={
            "file_id": uploaded_file_id,
            "machine_type": "laser",
            "config_json": json.dumps(custom_config),
        },
    )
    assert res.status_code == 200


def test_preview_invalid_file_id(client):
    """Несуществующий file_id → 400."""
    res = client.post(
        "/api/process/preview",
        data={"file_id": "nonexistent-id", "machine_type": "laser"},
    )
    assert res.status_code == 400


def test_export_returns_file(client, uploaded_file_id):
    """POST /api/process/export по file_id отдаёт файл."""
    res = client.post(
        "/api/process/export",
        data={"file_id": uploaded_file_id, "machine_type": "laser", "format": "png"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 0


def test_preview_fallback_direct_file(client, sample_chromakey_png):
    """POST /api/process/preview с файлом напрямую (без file_id) — fallback."""
    res = client.post(
        "/api/process/preview",
        files={"file": ("test.png", sample_chromakey_png, "image/png")},
        data={"machine_type": "laser"},
    )
    assert res.status_code == 200
    assert "images" in res.json()
```

### test_config_api.py

```python
"""Тесты роутера конфигурации — с изоляцией файловой системы."""
import pytest
from pathlib import Path


def test_get_config(client):
    """GET /api/config возвращает конфиг."""
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "config" in data
    assert "source" in data
    assert "warnings" in data


def test_get_defaults(client):
    """GET /api/config/defaults возвращает дефолты."""
    res = client.get("/api/config/defaults")
    assert res.status_code == 200
    data = res.json()
    assert "config" in data
    assert "processing" in data["config"]


def test_put_config_uses_tmp(tmp_path, monkeypatch):
    """PUT /api/config сохраняет конфиг во временный файл (изоляция)."""
    # Переопределяем поиск конфига на tmp_path
    from retouch import config as cfg_module
    tmp_config = tmp_path / "config.yaml"
    monkeypatch.setattr(cfg_module, "find_config_path", lambda: tmp_config)

    from fastapi.testclient import TestClient
    from ..main import app
    client = TestClient(app)

    # Получить текущий
    current = client.get("/api/config").json()

    # Сохранить (без изменений) — в tmp_path
    res = client.put(
        "/api/config",
        json={"config": current["config"]},
    )
    assert res.status_code == 200
    assert res.json()["saved"] is True
    assert tmp_config.exists()
```

### test_presets_api.py

```python
"""Тесты роутера пресетов — с изоляцией."""


def test_list_presets(client):
    """GET /api/presets возвращает список."""
    res = client.get("/api/presets")
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert isinstance(data["presets"], list)


def test_create_and_delete_preset(client, tmp_path, monkeypatch):
    """Создание и удаление пресета — в изолированной директории."""
    from retouch_ui.backend.routers import presets as presets_module
    monkeypatch.setattr(presets_module, "_presets_dir", lambda: tmp_path)

    # Создать
    res = client.post(
        "/api/presets",
        json={
            "name": "test-isolated",
            "config": {"processing": {"laser": {"brightness": 1.20}}},
        },
    )
    assert res.status_code == 200

    # Удалить
    res = client.delete("/api/presets/test-isolated")
    assert res.status_code == 200


def test_create_duplicate_preset(client, tmp_path, monkeypatch):
    """Нельзя создать пресет с существующим именем."""
    from retouch_ui.backend.routers import presets as presets_module
    monkeypatch.setattr(presets_module, "_presets_dir", lambda: tmp_path)

    client.post("/api/presets", json={"name": "dup-test", "config": {}})
    res = client.post("/api/presets", json={"name": "dup-test", "config": {}})
    assert res.status_code == 409
    client.delete("/api/presets/dup-test")
```

---

## Задача 2: Обновление тестов pipeline

### test_pipeline.py — дополнения

```python
"""Дополнительные тесты для нового API pipeline (после Фазы 0)."""


def test_process_steps_returns_pipeline_result(chromakey_image):
    """process_steps() возвращает PipelineResult без сохранения файлов."""
    result = proc.process_steps(
        input_path=chromakey_image,
        machine_type="laser",
    )
    assert isinstance(result, proc.PipelineResult)
    assert result.img_final is not None
    assert result.img_final.mode == "RGB"
    assert result.glow_size > 0
    assert result.face_brightness_before > 0
    assert result.face_brightness_after > 0


def test_process_preview_fixed_glow(chromakey_image):
    """process_preview() фиксирует glow на середине диапазона."""
    result = proc.process_preview(
        input_path=chromakey_image,
        machine_type="laser",
    )
    # Glow на середине: (40 + 80) // 2 = 60
    assert result.glow_size == 60


def test_process_preview_resizes(chromakey_image):
    """process_preview() уменьшает изображение до max_size."""
    result = proc.process_preview(
        input_path=chromakey_image,
        machine_type="laser",
        max_size=256,
    )
    assert result.width <= 256
    assert result.height <= 256


def test_process_export_creates_files(chromakey_image):
    """process_export() создаёт TIFF + PNG и освобождает промежуточные."""
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "output.tif"
        result = proc.process_export(
            input_path=chromakey_image,
            output_path=str(output),
            machine_type="laser",
        )
        assert output.exists()
        assert output.with_suffix(".png").exists()
        # Промежуточные освобождены
        assert result.img_chromakey is None
        assert result.img_final is not None


def test_process_backward_compatible(chromakey_image):
    """process() — обратная совместимая обёртка."""
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "output.tif"
        result = proc.process(
            input_path=chromakey_image,
            output_path=str(output),
            machine_type="laser",
        )
        assert output.exists()
```

---

## Задача 3: Тесты для Pydantic-модели и deep_merge

```python
"""Тесты Pydantic-модели конфигурации и deep_merge."""
import copy
from retouch.config import (
    validate_config, deep_merge, DEFAULTS,
    find_config_path, HAS_PYDANTIC,
)


def test_defaults_not_mutated_by_merge():
    """deep_merge не мутирует DEFAULTS."""
    original = copy.deepcopy(DEFAULTS)
    override = {"processing": {"laser": {"brightness": 9.99}}}
    result = deep_merge(DEFAULTS, override)

    # DEFAULTS не изменился
    assert DEFAULTS["processing"]["laser"]["brightness"] == original["processing"]["laser"]["brightness"]
    # result содержит override
    assert result["processing"]["laser"]["brightness"] == 9.99
    # Остальные ключи laser — из DEFAULTS
    assert "glow_size_min" in result["processing"]["laser"]


def test_deep_merge_nested():
    """deep_merge корректно сливает вложенные словари."""
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99}}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 99, "d": 3}}


def test_deep_merge_list_override():
    """deep_merge: список заменяется целиком, не сливается."""
    base = {"processing": {"laser": {"face_brightness_target": [200, 230]}}}
    override = {"processing": {"laser": {"face_brightness_target": [185, 210]}}}
    result = deep_merge(base, override)
    assert result["processing"]["laser"]["face_brightness_target"] == [185, 210]


def test_partial_yaml_merged():
    """Частичный yaml дополняется DEFAULTS через deep_merge."""
    partial = {"processing": {"laser": {"brightness": 1.30}}}
    result = deep_merge(DEFAULTS, partial)
    assert result["processing"]["laser"]["brightness"] == 1.30
    assert "glow_size_min" in result["processing"]["laser"]
    assert "vignette" in result


def test_config_model_validates_defaults():
    """DEFAULTS проходят валидацию без предупреждений."""
    warnings = validate_config(DEFAULTS)
    assert len(warnings) == 0, f"DEFAULTS have warnings: {warnings}"


def test_config_model_rejects_bad_brightness():
    """brightness вне диапазона → warning."""
    bad_config = deep_merge(DEFAULTS, {"processing": {"laser": {"brightness": 9.99}}})
    warnings = validate_config(bad_config)
    assert len(warnings) > 0


def test_config_model_rejects_inverted_ranges():
    """glow_size_min > glow_size_max → warning."""
    bad_config = deep_merge(DEFAULTS, {"processing": {"laser": {"glow_size_min": 100, "glow_size_max": 10}}})
    warnings = validate_config(bad_config)
    assert any("glow_size_min > glow_size_max" in w for w in warnings)


def test_find_config_path_returns_path_or_none():
    """find_config_path возвращает Path или None."""
    result = find_config_path()
    assert result is None or isinstance(result, Path)


@pytest.mark.skipif(not HAS_PYDANTIC, reason="Pydantic not installed")
def test_pydantic_model_available():
    """Pydantic модель доступна если установлен pydantic."""
    from retouch.config import RetouchConfig
    config = RetouchConfig()
    assert config.processing.laser.brightness > 0
```

---

## Чеклист приёмки

- [ ] `pytest retouch-ui/backend/tests/ -v` — все backend-тесты проходят
- [ ] `pytest tests/ -v` — все существующие тесты + новые pipeline-тесты проходят
- [ ] Backend API тесты покрывают: upload, preview (by file_id + fallback), export, config, presets
- [ ] Тесты Pydantic модели покрывают: валидацию, deep_merge, неизменяемость DEFAULTS
- [ ] Тест config/presets изолирован от реальной файловой системы (tmp_path / monkeypatch)
- [ ] Обратная совместимость process() проверена тестом
- [ ] Количество тестов ≥ 115 (было 89 + ~25 новых)
- [ ] Git-тег `phase4-done` создан

---

## Итоговая сводка по всем фазам

| Фаза | Часы | Ключевой результат |
|------|------|--------------------|
| Pre-0 | ~1 | Баг-фиксы, синхронизация версий, GIMP → experimental, shadow_noise удалён |
| Фаза 0 | 4–6 | process_steps/preview/export, PipelineResult, logging, deep_merge (deepcopy!), Pydantic (optional) |
| Фаза 1 | 6–8 | FastAPI backend: file_id upload, asyncio.to_thread, BackgroundTask cleanup, health+version |
| Фаза 2 | 8–12 | React + Vite frontend: до/после, слайдеры, диагностика, api.ts с file_id |
| Фаза 3 | 3–4 | Интеграция, пресеты, обработка ошибок, make ui, production-сборка |
| Фаза 4 | 3–4 | Тесты backend API + pipeline + Pydantic + изоляция |
| **Итого** | **25–35** | |
