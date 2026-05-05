# Granite Retouch — Дев-план рефакторинга и Web UI

**Версия плана**: 3.2 (исправления по результатам 2-го ревью)
**Дата**: 2026-05-05
**Проект**: granite-retouch v2.6.0
**Ограничения**: 4 ГБ RAM, локальное использование, русский язык UI

---

## Архитектурные решения (итог)

| Вопрос | Решение | Обоснование |
|--------|---------|-------------|
| Frontend-фреймворк | **React 19 + Vite** | 4 ГБ RAM — Next.js ест 600–1200 МБ, Vite 150–300 МБ |
| UI-стиль | **Плоский тёмный**, без glassmorphism | Инструмент для оценки яркости — без визуального шума |
| Предпросмотр | **До/После** (side-by-side или табы) | Слайдер-компаратор — развлечение, не рабочий инструмент |
| Backend | **FastAPI sidecar** (localhost:8001) | Python-пайплайн работает постоянно, нет overhead на subprocess |
| Light-тема | **Нет** | Фотоинструмент = тёмный фон, светлая тема искажает восприятие |
| CI/CD | **Нет** | Локальный инструмент, один оператор |
| Docker | **Нет** | 4 ГБ — Docker + 2 контейнера = swap |
| Прогресс экспорта | **Лог скрипта** (stdout FastAPI) | Достаточно для одного оператора |
| Config-валидация | **Pydantic BaseModel** (optional import) | Один источник истины: типы + диапазоны + документация. Conditional import — без Web UI Pydantic не нужен |
| Загрузка файлов | **file_id** (загрузить один раз, отправлять ID) | Передавать 5 МБ файл при каждом движении слайдера — плохой UX даже на localhost |
| CPU-bound в FastAPI | **asyncio.to_thread** | Pillow/numpy блокируют event loop; без этого /api/health недоступен во время обработки |
| CORS | **allow_origins=["*"]** | Локальный инструмент, один оператор; строгий CORS создаёт проблемы на нестандартных портах |

---

## Фазы и зависимости

```
Pre-0 (quick fixes)     ← независимые баг-фиксы, ~1 ч
    ↓ [git tag: pre0-done]
Фаза 0 (pipeline)       ← рефакторинг process(), ~4–6 ч
    ↓ [git tag: phase0-done]
Фаза 1 (backend)  ────── можно параллелить:
    ↓                   Фаза 2 (frontend) — с мок-API
Фаза 3 (интеграция)     ← связка backend+frontend, ~3–4 ч
    ↓ [git tag: phase3-done]
Фаза 4 (тесты)          ← покрытие, ~3–4 ч
```

**Критический путь**: Pre-0 → Фаза 0 → Фаза 1 → Фаза 3

Git-теги между фазами — чекпоинты для агента. Если фаза выполнена частично — откат к тегу.

---

## Файлы плана

| Файл | Содержание | Время |
|------|-----------|-------|
| [dev-plan-pre0-quickfixes.md](dev-plan-pre0-quickfixes.md) | Быстрые исправления до рефакторинга | ~1 ч |
| [dev-plan-phase0-pipeline.md](dev-plan-phase0-pipeline.md) | Рефакторинг process() → process_steps/preview/export | 4–6 ч |
| [dev-plan-phase1-backend.md](dev-plan-phase1-backend.md) | FastAPI backend API | 6–8 ч |
| [dev-plan-phase2-frontend.md](dev-plan-phase2-frontend.md) | React + Vite frontend | 8–12 ч |
| [dev-plan-phase3-integration.md](dev-plan-phase3-integration.md) | Интеграция, пресеты, экспорт | 3–4 ч |
| [dev-plan-phase4-tests.md](dev-plan-phase4-tests.md) | Тесты backend + frontend | 3–4 ч |

**Итого**: 25–35 часов

---

## Структура проекта (после всех фаз)

```
granite-retouch/
├── retouch/                        # Python-пакет (существующий)
│   ├── __init__.py                 # версия из pyproject.toml
│   ├── cli.py                      # + logging.basicConfig
│   ├── config.py                   # + deep_merge (deepcopy!), + Pydantic модель (optional), - version drift
│   ├── processing/
│   │   ├── __init__.py             # + публичные экспорты
│   │   ├── pipeline.py             # + process_steps, process_preview (с ресайзом!), process_export, PipelineResult
│   │   ├── chromakey.py            # без изменений
│   │   ├── glow.py                 # без изменений
│   │   ├── levels.py               # - print(), + face_region_top, + highlight_start, Breaking: check_face_brightness возвращает кортеж
│   │   └── vignette.py             # без изменений
│   ├── validation/                 # без изменений
│   └── gimp/                       # УДАЛЕНО (в ветку experimental/gimp, переопределение BACKLOG-005)
├── retouch-ui/
│   ├── backend/
│   │   ├── main.py                 # FastAPI app + asyncio.to_thread + version в health
│   │   ├── routers/
│   │   │   ├── process.py          # POST /upload, /process/preview (по file_id), /process/export + BackgroundTask cleanup
│   │   │   ├── config.py           # GET/PUT /config, /config/defaults (поиск пути делегирован retouch.config)
│   │   │   └── presets.py          # GET/POST/DELETE /presets
│   │   ├── schemas.py              # Pydantic модели
│   │   └── requirements.txt
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       ├── src/
│       │   ├── App.tsx
│       │   ├── main.tsx
│       │   ├── components/
│       │   │   ├── image-upload.tsx
│       │   │   ├── before-after.tsx
│       │   │   ├── step-selector.tsx
│       │   │   ├── params-panel.tsx
│       │   │   ├── machine-switch.tsx
│       │   │   ├── diagnostics-panel.tsx
│       │   │   ├── config-actions.tsx
│       │   │   └── export-buttons.tsx
│       │   ├── lib/
│       │   │   ├── api.ts          # uploadImage() → file_id, fetchPreview(fileId, ...)
│       │   │   ├── config-schema.ts
│       │   │   └── utils.ts
│       │   └── hooks/
│       │       ├── use-preview.ts
│       │       └── use-config.ts
│       └── index.html
├── presets/                         # YAML-пресеты
├── config.yaml                      # синхронизирован с DEFAULTS
├── pyproject.toml                   # версия = __init__.py, + pydantic как optional dep
└── Makefile                         # + make ui, make ui-backend, make ui-frontend
```

---

## Breaking Changes (суммарно по всем фазам)

| Функция | Было | Стало | Фаза | Влияние |
|---------|------|-------|------|---------|
| `check_face_brightness()` | Возвращает `Image` | Возвращает `(Image, float, float, float)` | 0 | test_levels.py — обновить |
| `load_config()` | Возвращает yaml как есть | deep_merge(yaml, DEFAULTS) — частичный yaml дополняется | 0 | Может изменить поведение при частичном config.yaml |
| `process()` | Монолит с I/O | Тонкая обёртка над `process_export()` | 0 | CLI не ломается |
| `retouch/gimp/` | В main | Удалено в ветку experimental/gimp | Pre-0 | CLI команда `retouch gimp` удалена |
| `shadow_noise` | В DEFAULTS и yaml | Удалён | Pre-0 | test_config.py — обновить |

---

## Критерии приёмки (общие)

- [ ] `make ui` запускает backend + frontend одной командой
- [ ] RAM в режиме разработки ≤ 2.5 ГБ (backend + frontend + OS)
- [ ] Загрузка PNG → предпросмотр за < 3 сек
- [ ] Изменение слайдера → обновление предпросмотра за < 3 сек (без повторной загрузки файла)
- [ ] Переключение laser/impact меняет параметры и результат
- [ ] До/После отображается side-by-side
- [ ] Промежуточные этапы доступны для просмотра
- [ ] Диагностика показывает face brightness, glow, black ratio
- [ ] Сохранение config.yaml из UI
- [ ] Экспорт TIFF/PNG в полном разрешении
- [ ] CLI работает без изменений (`retouch process` — обратная совместимость)
- [ ] /api/health доступен во время обработки изображения
- [ ] Временные файлы удаляются после обработки (нет утечки диска)
- [ ] DEFAULTS не мутируется при вызовах load_config()

---

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Предпросмотр > 3 сек на большом изображении | Средняя | Высокое | max_size=768px для preview; ресайз через thumbnail() |
| Рефакторинг pipeline ломает CLI | Низкая | Высокое | process() = обёртка; интеграционный CLI-тест перед каждым коммитом |
| Glow рандомизируется — preview нестабилен | Высокая | Среднее | В preview: glow_size = (min+max)//2, в diagnostics — «range 40–80» |
| 4 ГБ RAM не хватает при большом изображении | Средняя | Среднее | --workers 1; preview на уменьшенной копии; release_intermediates(); asyncio.to_thread |
| FastAPI crash при невалидном изображении | Низкая | Среднее | try/except в router; валидация файла перед обработкой |
| CPU-bound обработка блокирует event loop | Высокая | Среднее | asyncio.to_thread для всех вызовов pipeline |
| Утечка временных файлов на диске | Средняя | Среднее | BackgroundTask для FileResponse; TTL cleanup для uploaded files |
| PermissionError на Windows при временных файлах | Средняя | Низкое | img.close() перед передачей пути; tmp.close() ДО записи через PIL |
| pytest-asyncio конфликт с TestClient | Низкая | Среднее | asyncio_mode = "strict" в pyproject.toml; или убрать pytest-asyncio |

---

## История изменений

### v3.2 — исправления по 2-му ревью

7 находок, все подтверждены и устранены:

| # | Критичность | Находка | Статус | Где исправлено |
|---|-------------|---------|--------|---------------|
| N1 | 🔴 Critical | `BackgroundTasks().add_task()` возвращает None | ✅ Уже было правильно в v3.1 — `BackgroundTask` (singular) из `starlette.background` | phase1 |
| N2 | 🔴 Critical | `tempfile.BytesIO` не существует | ✅ Уже было правильно в v3.1 — `io.BytesIO`. Убран неиспользуемый `import tempfile` из conftest | phase4 |
| N3 | 🟠 High | `find_config_path()` не выделена в Phase 0 | ✅ Добавлена отдельная задача 11.5 + акцент в чеклисте и порядке выполнения | phase0 |
| N4 | 🟡 Medium | Нет `img.close()` в `process_preview` | ✅ Добавлен Windows-safe паттерн: `img.close()` + `tmp.close()` ДО записи через PIL | phase0 |
| N5 | 🟡 Medium | `asyncio.to_thread` + TestClient | ✅ Расширен раздел с обоснованием `strict` vs `auto` | phase4 |
| N6 | 🟢 Low | lifespan cleanup без try/except | ✅ Уже было правильно в v3.1 — `try/except` + `logger.exception()` | phase1 |
| N7 | 🟢 Low | `make ui` без явной зависимости на ui-install | ✅ `ui-install` с проверкой `node_modules` + `ui-force-install` | phase3 |

### v3.1 — исправления по 1-му ревью

18 находок, все устранены (подтверждено 2-м ревью):
- validate_result_black_ratio на img_final
- Правильные имена параметров apply_inner_glow
- Breaking Changes секция
- max_size реализован через thumbnail() + tmp + cleanup
- BackgroundTask для TIFF cleanup
- uploaded_at через time.time()
- deepcopy в deep_merge
- logging.basicConfig в cli.py
- Pydantic как optional dep
- GIMP override BACKLOG-005
- shadow_noise test update
- Удалён мёртвый кэш
- CORS allow_origins=["*"]
- tmp_path для тестов
- find_config_path extraction
- file_id перенесён в Phase 1
- asyncio.to_thread для CPU-bound
- version в health endpoint
- Git tag checkpoints
