# Фаза 4: Тесты

**Предыдущий этап**: [Фаза 3](dev-plan-phase3-integration.md)
**Время**: 3–4 часа
**Цель**: Покрыть backend API и критические сценарии UI. Не стремиться к 100% — покрыть важнейшие пути.

---

## Принцип тестирования

- **Backend**: pytest + FastAPI TestClient (синхронный, без uvicorn)
- **Frontend**: ручное тестирование (Playwright не нужен для локального инструмента с одним оператором)
- **Синтетические изображения**: как в существующих тестах — быстрое создание через PIL

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
def sample_chromakey_image():
    """Синтетическое изображение с синим хромакеем (512×512)."""
    img = Image.new("RGBA", (512, 512), (0, 0, 255, 255))  # синий фон
    # Белый субъект в центре
    for x in range(200, 312):
        for y in range(200, 312):
            img.putpixel((x, y), (255, 255, 255, 255))

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img.save(tmp.name, format="PNG")
        yield tmp.name

    Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def sample_image_file(sample_chromakey_image):
    """Файл-объект для загрузки через API."""
    with open(sample_chromakey_image, "rb") as f:
        yield f
```

### test_process.py

```python
"""Тесты роутера обработки изображений."""
import json


def test_health(client):
    """GET /api/health возвращает ok."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_preview_returns_images(client, sample_chromakey_image):
    """POST /api/process/preview возвращает base64-изображения."""
    with open(sample_chromakey_image, "rb") as f:
        res = client.post(
            "/api/process/preview",
            files={"file": ("test.png", f, "image/png")},
            data={"machine_type": "laser"},
        )
    assert res.status_code == 200
    data = res.json()

    # Проверяем структуру
    assert "images" in data
    assert "diagnostics" in data
    assert "warnings" in data

    # Все шаги присутствуют
    for step in ("chromakey", "glow", "leveled", "face_corrected", "final", "arch_mask"):
        assert step in data["images"]
        assert data["images"][step].startswith("data:image/png;base64,")

    # Диагностика содержит ожидаемые поля
    diag = data["diagnostics"]
    assert "glow_size" in diag
    assert "face_brightness_before" in diag
    assert "face_brightness_after" in diag


def test_preview_laser_vs_impact(client, sample_chromakey_image):
    """Laser и impact дают разный glow_size."""
    results = {}
    for machine in ("laser", "impact"):
        with open(sample_chromakey_image, "rb") as f:
            res = client.post(
                "/api/process/preview",
                files={"file": ("test.png", f, "image/png")},
                data={"machine_type": machine},
            )
        results[machine] = res.json()["diagnostics"]["glow_size"]

    # Laser glow 40-80, Impact glow 10-25 — не должны совпадать
    assert results["laser"] != results["impact"]


def test_preview_custom_config(client, sample_chromakey_image):
    """Переопределение параметров через config_json."""
    custom_config = {"processing": {"laser": {"brightness": 1.40}}}
    with open(sample_chromakey_image, "rb") as f:
        res = client.post(
            "/api/process/preview",
            files={"file": ("test.png", f, "image/png")},
            data={
                "machine_type": "laser",
                "config_json": json.dumps(custom_config),
            },
        )
    assert res.status_code == 200


def test_preview_invalid_image(client):
    """Ошибка при невалидном файле."""
    res = client.post(
        "/api/process/preview",
        files={"file": ("test.txt", b"not an image", "text/plain")},
        data={"machine_type": "laser"},
    )
    # 400 или 422
    assert res.status_code in (400, 422)


def test_export_returns_file(client, sample_chromakey_image):
    """POST /api/process/export отдаёт файл."""
    with open(sample_chromakey_image, "rb") as f:
        res = client.post(
            "/api/process/export",
            files={"file": ("test.png", f, "image/png")},
            data={"machine_type": "laser", "format": "png"},
        )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 0


def test_upload_and_preview_by_id(client, sample_chromakey_image):
    """Загрузка файла → preview по file_id."""
    # Шаг 1: загрузить
    with open(sample_chromakey_image, "rb") as f:
        upload_res = client.post(
            "/api/process/upload",
            files={"file": ("test.png", f, "image/png")},
        )
    assert upload_res.status_code == 200
    file_id = upload_res.json()["file_id"]

    # Шаг 2: preview по ID
    res = client.post(
        "/api/process/preview",
        data={"file_id": file_id, "machine_type": "laser"},
    )
    assert res.status_code == 200
    assert "images" in res.json()
```

### test_config_api.py

```python
"""Тесты роутера конфигурации."""


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


def test_put_config(client):
    """PUT /api/config сохраняет конфиг."""
    # Получить текущий
    current = client.get("/api/config").json()

    # Сохранить (без изменений)
    res = client.put(
        "/api/config",
        json={"config": current["config"]},
    )
    assert res.status_code == 200
    assert res.json()["saved"] is True
```

### test_presets_api.py

```python
"""Тесты роутера пресетов."""


def test_list_presets(client):
    """GET /api/presets возвращает список."""
    res = client.get("/api/presets")
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert isinstance(data["presets"], list)


def test_create_and_delete_preset(client):
    """Создание и удаление пресета."""
    # Создать
    res = client.post(
        "/api/presets",
        json={
            "name": "test-preset-001",
            "config": {"processing": {"laser": {"brightness": 1.20}}},
        },
    )
    assert res.status_code == 200

    # Проверить что появился в списке
    presets = client.get("/api/presets").json()["presets"]
    names = [p["name"] for p in presets]
    assert "test-preset-001" in names

    # Удалить
    res = client.delete("/api/presets/test-preset-001")
    assert res.status_code == 200

    # Проверить что удалён
    presets = client.get("/api/presets").json()["presets"]
    names = [p["name"] for p in presets]
    assert "test-preset-001" not in names


def test_create_duplicate_preset(client):
    """Нельзя создать пресет с существующим именем."""
    client.post("/api/presets", json={"name": "dup-test", "config": {}})
    res = client.post("/api/presets", json={"name": "dup-test", "config": {}})
    assert res.status_code == 409
    # Cleanup
    client.delete("/api/presets/dup-test")
```

---

## Задача 2: Обновление существующих тестов pipeline

### test_pipeline.py — дополнения

После рефакторинга Фазы 0 нужно обновить и дополнить тесты:

```python
"""Дополнительные тесты для нового API pipeline."""


def test_process_steps_returns_pipeline_result():
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


def test_process_preview_fixed_glow():
    """process_preview() фиксирует glow на середине диапазона."""
    result = proc.process_preview(
        input_path=chromakey_image,
        machine_type="laser",
    )
    # Glow должен быть на середине: (40 + 80) // 2 = 60
    assert result.glow_size == 60


def test_process_preview_resizes():
    """process_preview() уменьшает изображение до max_size."""
    result = proc.process_preview(
        input_path=chromakey_image,
        machine_type="laser",
        max_size=256,
    )
    assert result.width <= 256
    assert result.height <= 256


def test_process_export_creates_files():
    """process_export() создаёт TIFF + PNG."""
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


def test_process_backward_compatible():
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

## Задача 3: Тесты для Pydantic-модели конфига

```python
"""Тесты Pydantic-модели конфигурации."""
from retouch.config import RetouchConfig, validate_config, deep_merge, DEFAULTS


def test_config_model_validates_defaults():
    """DEFAULTS проходят Pydantic-валидацию."""
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


def test_deep_merge():
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
    # brightness переопределён
    assert result["processing"]["laser"]["brightness"] == 1.30
    # Остальные ключи laser — из DEFAULTS
    assert "glow_size_min" in result["processing"]["laser"]
    assert "vignette" in result
```

---

## Чеклист приёмки

- [ ] `pytest retouch-ui/backend/tests/ -v` — все backend-тесты проходят
- [ ] `pytest tests/ -v` — все существующие тесты + новые pipeline-тесты проходят
- [ ] Backend API тесты покрывают: preview, export, config, presets, upload
- [ ] Тесты Pydantic-модели покрывают: валидацию, deep_merge, частичные конфиги
- [ ] Обратная совместимость process() проверена тестом
- [ ] Количество тестов ≥ 110 (было 89 + ~20 новых)

---

## Итоговая сводка по всем фазам

| Фаза | Часы | Ключевой результат |
|------|------|--------------------|
| Pre-0 | ~1 | Баг-фиксы, синхронизация версий, удаление мёртвого кода |
| Фаза 0 | 4–6 | process_steps/preview/export, PipelineResult, logging, deep_merge, Pydantic |
| Фаза 1 | 6–8 | FastAPI backend с /process, /config, /presets |
| Фаза 2 | 8–12 | React + Vite frontend с до/после, слайдерами, диагностикой |
| Фаза 3 | 4–6 | Интеграция, пресеты, экспорт, обработка ошибок, make ui |
| Фаза 4 | 3–4 | Тесты backend API + pipeline + Pydantic |
| **Итого** | **26–37** | |
