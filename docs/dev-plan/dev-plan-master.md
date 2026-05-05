# Granite Retouch — Дев-план рефакторинга и Web UI

**Версия плана**: 3.0 (пересмотренный)
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
| Config-валидация | **Pydantic BaseModel** | Один источник истины: типы + диапазоны + документация |

---

## Фазы и зависимости

```
Pre-0 (quick fixes)     ← независимые баг-фиксы, ~1 ч
    ↓
Фаза 0 (pipeline)       ← рефакторинг process(), ~4–6 ч
    ↓
Фаза 1 (backend)  ────── можно параллелить:
    ↓                   Фаза 2 (frontend) — с мок-API
Фаза 3 (интеграция)     ← связка backend+frontend, ~4–6 ч
    ↓
Фаза 4 (тесты)          ← покрытие, ~3–4 ч
```

**Критический путь**: Pre-0 → Фаза 0 → Фаза 1 → Фаза 3

---

## Файлы плана

| Файл | Содержание | Время |
|------|-----------|-------|
| [dev-plan-pre0-quickfixes.md](dev-plan-pre0-quickfixes.md) | Быстрые исправления до рефакторинга | ~1 ч |
| [dev-plan-phase0-pipeline.md](dev-plan-phase0-pipeline.md) | Рефакторинг process() → process_steps/preview/export | 4–6 ч |
| [dev-plan-phase1-backend.md](dev-plan-phase1-backend.md) | FastAPI backend API | 6–8 ч |
| [dev-plan-phase2-frontend.md](dev-plan-phase2-frontend.md) | React + Vite frontend | 8–12 ч |
| [dev-plan-phase3-integration.md](dev-plan-phase3-integration.md) | Интеграция, пресеты, экспорт | 4–6 ч |
| [dev-plan-phase4-tests.md](dev-plan-phase4-tests.md) | Тесты backend + frontend | 3–4 ч |

**Итого**: 26–37 часов

---

## Структура проекта (после всех фаз)

```
granite-retouch/
├── retouch/                        # Python-пакет (существующий)
│   ├── __init__.py                 # версия из pyproject.toml
│   ├── cli.py
│   ├── config.py                   # + deep_merge, + Pydantic модель, - version drift
│   ├── processing/
│   │   ├── __init__.py             # + публичные экспорты
│   │   ├── pipeline.py             # + process_steps, process_preview, process_export, PipelineResult
│   │   ├── chromakey.py            # без изменений
│   │   ├── glow.py                 # без изменений
│   │   ├── levels.py               # - print(), + face_region_top, + highlight_start в конфиг
│   │   └── vignette.py             # без изменений
│   ├── validation/                 # без изменений
│   └── gimp/                       # УДАЛЕНО (в ветку experimental/gimp)
├── retouch-ui/
│   ├── backend/
│   │   ├── main.py                 # FastAPI app
│   │   ├── routers/
│   │   │   ├── process.py          # POST /process/preview, /process/export
│   │   │   ├── config.py           # GET/PUT /config, /config/defaults
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
│       │   │   ├── api.ts
│       │   │   ├── config-schema.ts
│       │   │   └── utils.ts
│       │   └── hooks/
│       │       ├── use-preview.ts
│       │       └── use-config.ts
│       └── index.html
├── presets/                         # YAML-пресеты
├── config.yaml                      # синхронизирован с DEFAULTS
├── pyproject.toml                   # версия = __init__.py
└── Makefile                         # + make ui, make ui-backend, make ui-frontend
```

---

## Критерии приёмки (общие)

- [ ] `make ui` запускает backend + frontend одной командой
- [ ] RAM в режиме разработки ≤ 2.5 ГБ (backend + frontend + OS)
- [ ] Загрузка PNG → предпросмотр за < 3 сек
- [ ] Изменение слайдера → обновление предпросмотра за < 3 сек
- [ ] Переключение laser/impact меняет параметры и результат
- [ ] До/После отображается side-by-side
- [ ] Промежуточные этапы доступны для просмотра
- [ ] Диагностика показывает face brightness, glow, black ratio
- [ ] Сохранение config.yaml из UI
- [ ] Экспорт TIFF/PNG в полном разрешении
- [ ] CLI работает без изменений (`retouch process` — обратная совместимость)

---

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Предпросмотр > 3 сек на большом изображении | Средняя | Высокое | max_size=768px для preview; кэш последнего запроса |
| Рефакторинг pipeline ломает CLI | Низкая | Высокое | process() = обёртка; интеграционный CLI-тест перед каждым коммитом |
| Glow рандомизируется — preview нестабилен | Высокая | Среднее | В preview: glow_size = (min+max)//2, в diagnostics — «range 40–80» |
| 4 ГБ RAM не хватает при большом изображении | Средняя | Среднее | --workers 1 для uvicorn; preview на уменьшенной копии; очистка PIL-объектов |
| FastAPI crash при невалидном изображении | Низкая | Среднее | try/except в router; валидация файла перед обработкой |
