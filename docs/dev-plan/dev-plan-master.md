# Granite Retouch — Дев-план рефакторинга и Web UI

**Версия плана**: 3.4 (исправления по аудиту — 19 находок + отмена удаления GIMP)
**Дата**: 2026-05-05
**Проект**: granite-retouch v2.6.0
**Ограничения**: 4 ГБ RAM, локальное использование, русский язык UI

---

## Изменения v3.4 относительно v3.3

| # | Критичность | Изменение |
|---|-------------|-----------|
| A1 | 🔴 Critical | `face_region_top` и `highlight_start` добавлены в DEFAULTS и config.yaml |
| A2 | 🔴 Critical | `img.close()` добавлен в `process_steps()` после chromakey-шага |
| A3 | 🔴 Critical | `PUT /api/config` делает `deep_merge(DEFAULTS, request.config)` перед сохранением |
| A4 | 🟠 High | `check_face_brightness()` — исправлен псевдокод, определена `subject_mask_arr` |
| A5 | 🟠 High | `process_preview()` — одно открытие изображения вместо двух |
| A6 | 🟠 High | Добавлена реализация `hooks/use-config.ts` |
| A7 | 🟠 High | `params-panel.tsx` и `config-actions.tsx` — заполнены каркасы реализаций |
| A8 | 🟠 High | Обновление BACKLOG.md добавлено в чеклисты каждой фазы |
| A9 | 🟡 Medium | Добавлен тест совпадения DEFAULTS и Pydantic-модели |
| A10 | 🟡 Medium | Версия проекта поднята до 3.0.0-dev (Breaking Changes) |
| A11 | 🟡 Medium | `_presets_dir()` использует `find_config_path()` как якорь |
| A12 | 🟡 Medium | Предупреждающий комментарий для `app.mount("/", StaticFiles(...))` |
| A13 | 🟡 Medium | Добавлены `__init__.py` для retouch_ui/backend/routers |
| A14 | 🟡 Medium | Добавлена задача обновления документации в Фазу 3 |
| A15 | 🟢 Low | Docstring для `release_intermediates()` — поведение после вызова |
| A16 | 🟢 Low | `MAX_UPLOADED_FILES = 50` — лимит загруженных файлов |
| A17 | 🟢 Low | `image-upload.tsx` — добавлен `useRef` и `onClick` для file input |
| A18 | 🟢 Low | Обновление CHANGELOG.md добавлено в Фазу 3 |
| A19 | 🟢 Low | RAM-оценка уточнена: ~100 МБ при 2048×2048 (пик 150 МБ с numpy) |
| — | 🔵 Decision | **GIMP-пайплайн сохранён** (отмена задачи Pre-0 №5 из v3.3). BACKLOG-005 решение: пометка experimental |

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
| CORS | **allow_origins=["\*"]** | Локальный инструмент, один оператор; строгий CORS создаёт проблемы на нестандартных портах |
| GIMP-пайплайн | **Сохранён** с пометкой experimental | Основной путь — Pillow (`retouch process`). GIMP остаётся для отладки и будущих экспериментов |

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

**Итого**: 22–34 часов

---

## Структура проекта (после всех фаз)

```
granite-retouch/
├── retouch/                        # Python-пакет (существующий)
│   ├── __init__.py                 # версия 3.0.0-dev из pyproject.toml
│   ├── cli.py                      # + logging.basicConfig, GIMP команда сохранена (experimental)
│   ├── config.py                   # + deep_merge (deepcopy!), + Pydantic модель (optional), + face_region_top, highlight_start в DEFAULTS
│   ├── processing/
│   │   ├── __init__.py             # + публичные экспорты
│   │   ├── pipeline.py             # + process_steps, process_preview (с ресайзом!), process_export, PipelineResult, img.close()
│   │   ├── chromakey.py            # без изменений
│   │   ├── glow.py                 # без изменений
│   │   ├── levels.py               # - print(), + face_region_top, + highlight_start, Breaking: check_face_brightness возвращает кортеж
│   │   └── vignette.py             # без изменений
│   ├── validation/                 # без изменений
│   └── gimp/                       # СОХРАНЕНО — experimental / not recommended
│       ├── __init__.py
│       └── runner.py               # предупреждение при запуске
├── retouch_process.scm             # СОХРАНЁН — Script-Fu для GIMP
├── retouch_ui/
│   ├── __init__.py                 # пустой (для relative imports)
│   ├── backend/
│   │   ├── __init__.py             # пустой
│   │   ├── main.py                 # FastAPI app + asyncio.to_thread + version в health
│   │   ├── routers/
│   │   │   ├── __init__.py         # пустой
│   │   │   ├── process.py          # POST /upload, /process/preview (по file_id), /process/export + BackgroundTask cleanup + MAX_UPLOADED_FILES
│   │   │   ├── config.py           # GET/PUT /config (deep_merge перед сохранением!), /config/defaults
│   │   │   └── presets.py          # GET/POST/DELETE /presets (_presets_dir через find_config_path)
│   │   ├── schemas.py              # Pydantic модели
│   │   └── requirements.txt
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       ├── src/
│       │   ├── App.tsx
│       │   ├── main.tsx
│       │   ├── components/
│       │   │   ├── image-upload.tsx  # + useRef + onClick для file input
│       │   │   ├── before-after.tsx
│       │   │   ├── step-selector.tsx
│       │   │   ├── params-panel.tsx  # ЗАПОЛНЕН каркас реализации
│       │   │   ├── machine-switch.tsx
│       │   │   ├── diagnostics-panel.tsx
│       │   │   ├── config-actions.tsx # ЗАПОЛНЕН каркас реализации
│       │   │   └── export-buttons.tsx
│       │   ├── lib/
│       │   │   ├── api.ts          # uploadImage() → file_id, fetchPreview(fileId, ...)
│       │   │   ├── config-schema.ts
│       │   │   └── utils.ts
│       │   └── hooks/
│       │       ├── use-preview.ts
│       │       └── use-config.ts   # ДОБАВЛЕНА полная реализация
│       └── index.html
├── presets/                         # YAML-пресеты
├── config.yaml                      # синхронизирован с DEFAULTS (+ face_region_top, highlight_start)
├── pyproject.toml                   # версия 3.0.0-dev, + pydantic как optional dep
└── Makefile                         # + make ui, make ui-backend, make ui-frontend, make ui-prod
```

---

## Breaking Changes (суммарно по всем фазам)

| Функция | Было | Стало | Фаза | Влияние |
|---------|------|-------|------|---------|
| `check_face_brightness()` | Возвращает `Image` | Возвращает `(Image, float, float, float)` | 0 | test_levels.py — обновить |
| `load_config()` | Возвращает yaml как есть | `deep_merge(DEFAULTS, yaml)` — частичный yaml дополняется | 0 | Может изменить поведение при частичном config.yaml |
| `process()` | Монолит с I/O | Тонкая обёртка над `process_export()` | 0 | CLI не ломается |
| `shadow_noise` | В DEFAULTS и yaml | Удалён | Pre-0 | test_config.py — обновить |
| Версия | `2.6.0` | `3.0.0-dev` | Pre-0 | SemVer — Breaking Changes |

**Примечание**: GIMP-пайплайн **сохранён** — команда `retouch gimp` остаётся с пометкой experimental.

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
- [ ] `retouch gimp` работает с предупреждением «experimental»
- [ ] /api/health доступен во время обработки изображения
- [ ] Временные файлы удаляются после обработки (нет утечки диска)
- [ ] DEFAULTS не мутируется при вызовах load_config()
- [ ] BACKLOG.md обновлён — завершённые задачи отмечены
- [ ] Документация обновлена — новые параметры, Web UI, GIMP experimental

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
| Утечка временных файлов на диске | Средняя | Среднее | BackgroundTask для FileResponse; TTL cleanup для uploaded files; MAX_UPLOADED_FILES=50 |
| PermissionError на Windows при временных файлах | Средняя | Низкое | img.close() перед передачей пути; tmp.close() ДО записи через PIL |
| pytest-asyncio конфликт с TestClient | Низкая | Среднее | asyncio_mode = "strict" в pyproject.toml; или убрать pytest-asyncio |
| Preview timeout на очень больших изображениях | Низкая | Среднее | asyncio.wait_for(timeout=15.0) + HTTP 408 + подсказка уменьшить изображение |
| _uploaded_files race condition при --workers > 1 | Низкая | Низкое | --workers 1; комментарий о необходимости threading.Lock при масштабировании |
| DEFAULTS рассинхрон с Pydantic-моделью | Средняя | Среднее | Тест `test_defaults_match_pydantic` при каждом изменении DEFAULTS |
| GIMP-пайплайн получает баг-репорт | Средняя | Низкое | Пометка experimental + предупреждение; приоритет — Pillow-пайплайн |

---

## История изменений

### v3.4 — исправления по аудиту (19 находок + отмена удаления GIMP)

| # | Критичность | Находка | Статус | Где исправлено |
|---|-------------|---------|--------|---------------|
| A1 | 🔴 Critical | `face_region_top` и `highlight_start` не в DEFAULTS | ✅ Добавлены в DEFAULTS, config.yaml, Pydantic | phase0 |
| A2 | 🔴 Critical | `process_steps()` не закрывает исходное изображение | ✅ Добавлен `img.close()` после chromakey | phase0 |
| A3 | 🔴 Critical | `PUT /api/config` затирает частичный конфиг | ✅ `deep_merge(DEFAULTS, request.config)` перед сохранением | phase1 |
| A4 | 🟠 High | `check_face_brightness()` — неполный псевдокод | ✅ Определена `subject_mask_arr` | phase0 |
| A5 | 🟠 High | `process_preview()` дважды открывает изображение | ✅ Один open + thumbnail в памяти | phase0 |
| A6 | 🟠 High | `use-config.ts` не определён | ✅ Добавлена полная реализация | phase2 |
| A7 | 🟠 High | `params-panel.tsx`, `config-actions.tsx` — заглушки | ✅ Заполнены каркасы | phase2 |
| A8 | 🟠 High | BACKLOG.md не обновляется по завершении фаз | ✅ Добавлено в чеклисты всех фаз | все |
| A9 | 🟡 Medium | DEFAULTS и Pydantic — два источника истины | ✅ Добавлен тест совпадения | phase4 |
| A10 | 🟡 Medium | Версия не поднята до 3.0.0 | ✅ Версия 3.0.0-dev в Pre-0 | pre0 |
| A11 | 🟡 Medium | `_presets_dir()` — хрупкая навигация | ✅ Использует `find_config_path()` как якорь | phase1 |
| A12 | 🟡 Medium | `app.mount("/", StaticFiles)` — конфликт с API | ✅ Предупреждающий комментарий | phase3 |
| A13 | 🟡 Medium | Relative imports без `__init__.py` | ✅ Добавлены `__init__.py` | phase1 |
| A14 | 🟡 Medium | Документация не обновляется | ✅ Добавлена задача в Фазу 3 | phase3 |
| A15 | 🟢 Low | `release_intermediates()` — нет docstring о поведении | ✅ Добавлен docstring | phase0 |
| A16 | 🟢 Low | Нет лимита загруженных файлов | ✅ `MAX_UPLOADED_FILES = 50` | phase1 |
| A17 | 🟢 Low | `image-upload.tsx` — скрытый input без onClick | ✅ Добавлен `useRef` + `onClick` | phase2 |
| A18 | 🟢 Low | CHANGELOG.md не обновляется | ✅ Добавлена задача в Фазу 3 | phase3 |
| A19 | 🟢 Low | RAM-оценка PipelineResult неточна | ✅ Уточнена: ~100 МБ (пик 150 МБ) | phase0 |
| — | 🔵 Decision | GIMP-пайплайн удаляется в v3.3 | ❌ Отменено — GIMP сохранён с пометкой experimental | pre0 |

### v3.3 — исправления по 3-му аудиту (17 находок)

(без изменений — см. v3.3)

### v3.2 — исправления по 2-му ревью (7 находок)

(без изменений — см. v3.3)

### v3.1 — исправления по 1-му ревью (18 находок)

(без изменений — см. v3.3)
