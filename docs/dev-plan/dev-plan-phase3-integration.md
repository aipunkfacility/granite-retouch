# Фаза 3: Интеграция и Polish

**Предыдущий этап**: [Фаза 2](dev-plan-phase2-frontend.md)
**Следующий этап**: [Фаза 4](dev-plan-phase4-tests.md)
**Время**: 3–4 часа (сокращено — file_id уже в Фазе 1)
**Цель**: Связать frontend и backend в рабочее приложение, добавить пресеты, обработку ошибок.

---

## Контекст

Основная интеграция (file_id, upload endpoint) уже реализована в Фазе 1. Эта фаза фокусируется на:
- Пресетах (готовые YAML + UI)
- Обработке ошибок (frontend ↔ backend)
- Makefile и production-сборке
- Управлении памятью

---

## Задача 1: Пресеты — готовые наборы

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

---

## Задача 2: Обработка ошибок

### Frontend — типы ошибок

| Ошибка | UI-реакция |
|--------|-----------|
| Backend недоступен (fetch failed) | Жёлтый баннер вверху: «Backend не запущен. Запустите: make ui-backend» |
| 422 — нет хромакея | Предупреждение: «Синий фон не обнаружен. Обработать без хромакея?» + кнопка «Продолжить» (отправляет `no_validate: true`) |
| 422 — невалидное изображение | Красный alert: «Файл не является изображением или повреждён» |
| 500 — ошибка обработки | Красный alert с текстом ошибки из backend |
| Timeout (> 10 сек) | Предупреждение: «Обработка занимает долго. Попробуйте уменьшить изображение.» |

### Backend — error handling

Уже реализовано в Фазе 1 через try/except в routers. Дополнительно:
- Логирование через `logging.exception()` для 500 ошибок
- `asyncio.wait_for()` для preview (макс 15 сек)
- Graceful shutdown при Ctrl+C (`lifespan` cleanup)

---

## Задача 3: Makefile — единая точка входа

Добавить в корневой `Makefile`:

```makefile
# === Web UI ===

ui-backend:      ## Запустить FastAPI backend
	cd retouch-ui/backend && uvicorn main:app --port 8001 --reload --workers 1

ui-frontend:     ## Запустить Vite frontend
	cd retouch-ui/frontend && npm run dev

ui:              ## Запустить backend + frontend
	cd retouch-ui/frontend && npx concurrently -n backend,frontend -c blue,green \
		"cd ../backend && uvicorn main:app --port 8001 --workers 1" \
		"npm run dev"

ui-install:      ## Установить зависимости frontend
	cd retouch-ui/frontend && npm install

ui-build:        ## Сборка frontend для продакшена
	cd retouch-ui/frontend && npm run build
```

---

## Задача 4: Production-сборка frontend

```bash
cd retouch-ui/frontend && npm run build
```

Результат — `retouch-ui/frontend/dist/` со статическими файлами.

FastAPI раздаёт статику:

```python
# main.py — добавить после всех роутеров
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```

При таком подходе нужен только один процесс: `uvicorn main:app --port 8001`. Frontend доступен на `http://localhost:8001`.

---

## Задача 5: Управление памятью

При 4 ГБ RAM критично не допускать утечек:

### Backend

1. **Загруженные изображения**: TTL 30 минут, cleanup при shutdown, `uploaded_at` установлен корректно (реализовано в Фазе 1)
2. **PIL Image**: закрывать после использования (`img.close()`)
3. **PipelineResult**: вызывать `release_intermediates()` в export-режиме (реализовано в Фазе 0)
4. **Временные файлы экспорта**: `BackgroundTask` для удаления (реализовано в Фазе 1)

### Frontend

1. **base64 изображения**: не хранить в состоянии больше 6 изображений одновременно
2. **Object URLs**: освобождать через `URL.revokeObjectURL()` после использования
3. **Debounce**: предотвращает множественные параллельные запросы

---

## Чеклист приёмки

- [ ] `make ui` запускает оба сервера одной командой
- [ ] Frontend доступен на `http://localhost:5173`
- [ ] Backend доступен на `http://localhost:8001`
- [ ] Загрузка изображения → fileId получен
- [ ] Предпросмотр по fileId за < 3 сек
- [ ] Движение слайдера → обновление предпросмотра за < 3 сек (без пересылки файла)
- [ ] Пресеты загружаются из `presets/` директории
- [ ] Создание нового пресета через UI сохраняет YAML-файл
- [ ] Экспорт TIFF/PNG скачивает файл
- [ ] Backend недоступен → жёлтый баннер в UI
- [ ] Нет хромакея → предупреждение с опцией продолжить
- [ ] RAM в режиме разработки ≤ 2.5 ГБ
- [ ] Временные файлы удаляются после обработки
- [ ] `make ui-build` собирает статику в `dist/`
- [ ] Git-тег `phase3-done` создан
