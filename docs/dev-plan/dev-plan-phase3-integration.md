# Фаза 3: Интеграция и Polish

**Предыдущий этап**: [Фаза 2](dev-plan-phase2-frontend.md)
**Следующий этап**: [Фаза 4](dev-plan-phase4-tests.md)
**Время**: 4–6 часов
**Цель**: Связать frontend и backend в рабочее приложение, добавить пресеты, экспорт, обработку ошибок.

---

## Контекст

К концу Фазы 2 frontend работает с мок-API или с реальным backend (если Фаза 1 уже готова). В этой фазе мы проверяем, что всё работает вместе, и добавляем фичи, которые требуют и frontend, и backend.

---

## Задача 1: Связка frontend ↔ backend

### Проблема: файл передаётся на каждый запрос

Текущий дизайн: при каждом движении слайдера frontend отправляет **весь файл** + параметры → backend обрабатывает → возвращает base64.

При debounce 300ms и изображении 5 МБ — это ~15 МБ/сек сети (loopback). Для localhost это не проблема, но при медленных дисках или большом изображении — может быть узким местом.

### Оптимизация: загрузить файл один раз, отправлять только конфиг

**Backend**: добавить endpoint для загрузки файла с получением ID:

```python
# routers/process.py —新增

import uuid
from typing import Dict, Tuple

# In-memory хранилище загруженных файлов
_uploaded_files: Dict[str, Tuple[str, dict]] = {}  # id → (path, metadata)


@router.post("/process/upload")
async def upload_image(file: UploadFile = File(...)):
    """Загрузить изображение, получить ID для последующих запросов."""
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "Файл слишком большой (макс. 20 МБ)")

    file_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(contents)
        _uploaded_files[file_id] = (tmp.name, {
            "original_name": file.filename,
            "size": len(contents),
        })

    return {"file_id": file_id}


@router.post("/process/preview")
async def process_preview(
    file_id: str = Form(None),        # Новый способ: по ID
    file: UploadFile = File(None),    # Старый способ: файл напрямую
    machine_type: str = Form("laser"),
    config_json: str | None = Form(None),
):
    """Предпросмотр — по file_id или прямой загрузке."""
    # Определяем путь к файлу
    if file_id and file_id in _uploaded_files:
        tmp_path = _uploaded_files[file_id][0]
    elif file:
        # Fallback: прямая загрузка
        contents = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
    else:
        raise HTTPException(400, "Нужен file_id или файл")

    # ... остальной код обработки без изменений ...
```

**Frontend**: загрузить файл один раз при выборе, затем отправлять только `file_id`:

```typescript
// api.ts
export async function uploadImage(file: File): Promise<{ file_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/process/upload`, {
    method: "POST",
    body: formData,
  });
  return res.json();
}

export async function fetchPreview(
  fileId: string,                    // ID вместо File
  machineType: "laser" | "impact",
  configOverride?: Record<string, any>,
): Promise<PreviewResult> {
  const formData = new FormData();
  formData.append("file_id", fileId);
  formData.append("machine_type", machineType);
  if (configOverride) {
    formData.append("config_json", JSON.stringify(configOverride));
  }
  // ...
}
```

**Cleanup**: загруженные файлы удалять через TTL (30 минут неактивности) или при shutdown.

---

## Задача 2: Пресеты — готовые наборы

Создать директорию `presets/` с YAML-файлами:

**`presets/laser-default.yaml`**:
```yaml
processing:
  laser:
    brightness: 1.18
    glow_size_min: 40
    glow_size_max: 80
    glow_opacity_min: 30
    glow_opacity_max: 40
    face_brightness_target: [230, 245]
vignette:
  vertical_offset: 0.10
  vertical_diameter: 0.50
  blur_radius: 60
  headroom: 0.60
  horizontal_oversize: 0.20
```

**`presets/laser-dark-portrait.yaml`**:
```yaml
processing:
  laser:
    brightness: 1.30
    glow_size_min: 50
    glow_size_max: 90
    glow_opacity_min: 25
    glow_opacity_max: 35
    face_brightness_target: [235, 250]
vignette:
  headroom: 0.55
  horizontal_oversize: 0.25
```

**`presets/impact-default.yaml`**:
```yaml
processing:
  impact:
    brightness: 1.00
    glow_size_min: 10
    glow_size_max: 25
    glow_opacity_min: 60
    glow_opacity_max: 80
    face_brightness_target: [185, 210]
vignette:
  vertical_offset: 0.10
  vertical_diameter: 0.50
  blur_radius: 60
  headroom: 0.60
  horizontal_oversize: 0.20
```

**`presets/impact-soft.yaml`**:
```yaml
processing:
  impact:
    brightness: 1.05
    glow_size_min: 15
    glow_size_max: 30
    glow_opacity_min: 50
    glow_opacity_max: 70
    face_brightness_target: [190, 215]
vignette:
  blur_radius: 80
  headroom: 0.65
```

Frontend получает пресеты через `GET /api/presets`. При выборе пресета — применить его конфиг к слайдерам.

---

## Задача 3: Обработка ошибок

### Frontend — типы ошибок

| Ошибка | UI-реакция |
|--------|-----------|
| Backend недоступен (fetch failed) | Жёлтый баннер вверху: «Backend не запущен. Запустите: make ui-backend» |
| 422 — нет хромакея | Предупреждение: «Синий фон не обнаружен. Обработать без хромакея?» + кнопка «Продолжить» (отправляет `no_validate: true`) |
| 422 — невалидное изображение | Красный alert: «Файл не является изображением или повреждён» |
| 500 — ошибка обработки | Красный alert с текстом ошибки из backend |
| Timeout (> 10 сек) | Предупреждение: «Обработка занимает долго. Попробуйте уменьшить изображение.» |

### Backend — error handling

Уже реализовано в Фазе 1 через try/except в routers. Добавить:
- Логирование через `logging.exception()` для 500 ошибок
- Graceful shutdown при Ctrl+C (очистка временных файлов)
- Timeout через `asyncio.wait_for()` для preview (макс 10 сек)

---

## Задача 4: Makefile — единая точка входа

Добавить в корневой `Makefile`:

```makefile
# === Web UI ===

ui-backend:      ## Запустить FastAPI backend
	cd retouch-ui/backend && uvicorn main:app --port 8001 --reload --workers 1

ui-frontend:     ## Запустить Vite frontend
	cd retouch-ui/frontend && npm run dev

ui:              ## Запустить backend + frontend
	npx concurrently -n backend,frontend -c blue,green \
		"cd retouch-ui/backend && uvicorn main:app --port 8001 --workers 1" \
		"cd retouch-ui/frontend && npm run dev"

ui-install:      ## Установить зависимости frontend
	cd retouch-ui/frontend && npm install

ui-build:        ## Сборка frontend для продакшена
	cd retouch-ui/frontend && npm run build
```

**Примечание**: `concurrently` добавляется как dev-зависимость в `retouch-ui/frontend/package.json`:
```bash
cd retouch-ui/frontend && npm install -D concurrently
```

---

## Задача 5: Production-сборка frontend

```bash
cd retouch-ui/frontend && npm run build
```

Результат — `retouch-ui/frontend/dist/` со статическими файлами.

Для раздачи статики можно использовать:
- FastAPI напрямую (mount `dist/` как static files)
- Отдельный nginx
- Просто открыть `dist/index.html` в браузере (но API-запросы не сработают без прокси)

**Простейший вариант**: FastAPI раздаёт статику:

```python
# main.py — добавить
from fastapi.staticfiles import StaticFiles

# После всех роутеров:
app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```

При таком подходе нужен только один процесс: `uvicorn main:app --port 8001`. Frontend доступен на `http://localhost:8001`.

---

## Задача 6: Управление памятью

При 4 ГБ RAM критично не допускать утечек:

### Backend

1. **Временные файлы**: удалять после обработки (уже в `finally` блоках)
2. **Загруженные изображения**: TTL 30 минут, cleanup при shutdown
3. **PIL Image**: закрывать после использования (`img.close()`)
4. **PipelineResult**: вызывать `release_intermediates()` в export-режиме

```python
# Добавить в main.py
import atexit
import time

_CLEANUP_INTERVAL = 1800  # 30 минут

def _cleanup_uploaded_files():
    """Удалить устаревшие загруженные файлы."""
    now = time.time()
    to_delete = [
        fid for fid, (path, meta) in _uploaded_files.items()
        if now - meta.get("uploaded_at", now) > _CLEANUP_INTERVAL
    ]
    for fid in to_delete:
        Path(_uploaded_files[fid][0]).unlink(missing_ok=True)
        del _uploaded_files[fid]

atexit.register(lambda: [
    Path(p).unlink(missing_ok=True)
    for p, _ in _uploaded_files.values()
])
```

### Frontend

1. **base64 изображения**: не хранить в состоянии больше 6 изображений одновременно
2. **Object URLs**: освобождать через `URL.revokeObjectURL()` после использования
3. **Debounce**: предотвращает множественные параллельные запросы

---

## Чеклист приёмки

- [ ] `make ui` запускает оба сервера одной командой
- [ ] Frontend доступен на `http://localhost:5173`
- [ ] Backend доступен на `http://localhost:8001`
- [ ] Загрузка изображения → предпросмотр за < 3 сек
- [ ] Движение слайдера → обновление предпросмотра за < 3 сек
- [ ] Пресеты загружаются из `presets/` директории
- [ ] Создание нового пресета через UI сохраняет YAML-файл
- [ ] Экспорт TIFF/PNG скачивает файл
- [ ] Backend недоступен → жёлтый баннер в UI
- [ ] Нет хромакея → предупреждение с опцией продолжить
- [ ] RAM в режиме разработки ≤ 2.5 ГБ
- [ ] Временные файлы удаляются после обработки
- [ ] `make ui-build` собирает статику в `dist/`
