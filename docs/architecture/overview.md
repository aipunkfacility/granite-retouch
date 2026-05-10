# Архитектура проекта

## Структура каталогов

```
granite-retouch/
├── retouch/                     # Python-пакет (ядро)
│   ├── __init__.py
│   ├── __main__.py              # python -m retouch
│   ├── cli.py                   # CLI: process, validate, gimp, order
│   ├── config.py                # Загрузка config.yaml + defaults
│   ├── processing/
│   │   ├── chromakey.py         # Удаление синего фона + fringe removal
│   │   ├── analysis.py          # Преданализ: 13 метрик + ImageAnalytics dataclass
│   │   ├── glow.py              # Glow: inner (A.5) + outer + адаптивные параметры (D.1 детерминировано)
│   │   ├── levels.py            # Levels (адаптивный) + _adaptive_levels_factor
│   │   ├── face_correction.py   # check_face_brightness() + _curves_correction()
│   │   ├── face_region.py       # Детекция лица (C.1) + генерация масок (C.2)
│   │   ├── unsharp.py           # apply_unsharp_mask() + _adaptive_unsharp_percent()
│   │   ├── shadow_noise.py      # add_shadow_noise() — шум в тенях для impact
│   │   ├── export.py            # BMP/PNG экспорт + Jarvis/Stucki дизеринг
│   │   ├── vignette.py          # Арховая виньетка
│   │   └── pipeline.py          # Полный пайплайн + PipelineContext + PipelineResult
│   ├── gimp/
│   │   └── runner.py            # Поиск и запуск GIMP (experimental)
│   └── validation/
│       ├── image.py             # Валидация входного изображения
│       └── order.py             # Валидация order.json по schema.json
├── .agents/skills/              # ИИ-агенты (Antigravity IDE)
│   ├── retouch-analyzer/        # Анализ фото → analyzer_output
│   ├── retouch-prompter/        # Сборка промпта из блоков
│   │   └── prompt_blocks/       # Атомарные промпт-блоки
│   └── retouch-postprocessing/  # Чек-лист Photoshop
├── knowledge/                   # База знаний (станки, принципы)
├── orders/                      # Система заказов
│   ├── schema.json              # JSON-схема
│   ├── template/                # Шаблон нового заказа
│   └── active/                  # Активные заказы
├── retouch_ui/                  # Web UI
│   ├── backend/                 # FastAPI sidecar (localhost:8000)
│   │   ├── main.py              # App + lifespan + CORS + StaticFiles
│   │   ├── schemas.py           # Pydantic-модели запросов/ответов (D.4 валидация)
│   │   ├── cache.py             # LRU preview-кэш (OrderedDict + stable hash)
│   │   ├── routers/
│   │   │   ├── process.py       # /upload, /process/preview, /process/export
│   │   │   ├── config.py        # GET/PUT /config, /config/defaults
│   │   │   └── presets.py       # GET/POST/DELETE /presets
│   │   └── tests/               # Backend API тесты (31 тест)
│   └── frontend/                # React + Vite
│       ├── src/                 # Компоненты, хуки, overlays
│       │   ├── hooks/use-preview.ts  # Preview hook + version counter (D.8.3)
│       │   ├── face-oval-overlay.tsx # FaceOval интерактивный овал (E.1)
│       │   └── vignette-overlay.tsx  # Виньетка с drag (D.8)
│       └── dist/                # Production-сборка (gitignore)
├── presets/                     # YAML-пресеты (laser-default, impact-soft, ...)
├── tests/                       # Автотесты (266+ тестов)
│   ├── conftest.py              # Фикстуры + sample_pipeline_context (C.4)
│   ├── test_chromakey.py        # 7 тестов
│   ├── test_glow.py             # 9 тестов (добавлен test_deterministic_glow_midpoint)
│   ├── test_levels.py           # 28 тестов
│   ├── test_face_region.py      # 12 тестов — C.1 детекция, C.2 маски
│   ├── test_analysis.py         # 9 тестов
│   ├── test_skill_routing.py    # 5 тестов
│   ├── test_vignette.py         # 7 тестов
│   ├── test_validation.py       # 20 тестов
│   ├── test_config.py           # 35 тестов
│   ├── test_order_schema.py     # 26 тестов
│   ├── test_pipeline.py         # 18 тестов
│   ├── test_cli_integration.py  # 1 тест
│   ├── test_bugfixes_a.py       # 15 тестов — A.1–A.5 регрессия
│   ├── test_architecture_b.py   # 14 тестов — B.1–B.3 архитектура
│   ├── test_audit_fixes.py      # 7 тестов — D.4, D.6, F.1
│   ├── test_quality_f.py        # 8 тестов — F.2 метрики, F.3 BMP валидация
│   └── test_regression_g.py     # 16 тестов — G.1 P0, G.2 P1, G.3 интеграция
├── docs/                        # Документация
├── config.yaml                  # Параметры обработки
├── pyproject.toml               # Пакетная конфигурация
├── Makefile                     # Шорткаты (make test, make process, ...)
├── AGENTS.md                    # Агентский навигатор
├── BACKLOG.md                   # Product backlog
├── CHANGELOG.md                 # История изменений
└── README.md                    # Обзор проекта
```

## Поток данных

```
source.jpg ──→ [retouch-analyzer] ──→ order.json (analyzer_output)
                                               ↓
                 [retouch-prompter] ──→ prompt.md + order.json (final_prompt)
                                               ↓
                 [Nano Banana] ──→ ai.png (синий хромакей #0000FF)
                                               ↓
                 [retouch process] ──→ analytics (13 метрик, ImageAnalytics dataclass)
                                          ↓
                              [Face Detection (C.1)] → FaceOval
                                          ↓
                              [Face Mask + Hair Mask (C.2)]
                                          ↓
                              [Glow ← analytics, детерминировано (D.1)] → [Levels ← analytics + mask] →
                              [Face Brightness ← face_mask (C.3)] → [Unsharp ← analytics + mask] →
                              [Shadow Noise + Floor (impact)] → [White Ceiling Clamp] →
                              [Vignette] → [Export BMP + Post-Validation]
                                               ↓
                                 final.bmp + final.png (чёрный фон)
```

## Модули обработки

| Модуль | Файл | Вход | Выход | Зависимости |
|--------|------|------|-------|-------------|
| Chromakey | `chromakey.py` | RGBA | RGBA + mask (L) | numpy, scipy |
| Analytics | `analysis.py` | L + mask | ImageAnalytics (dataclass) | numpy |
| **Face Detection** | **`face_region.py`** | **L + mask** | **FaceOval (dict)** | **numpy** |
| **Face Mask** | **`face_region.py`** | **FaceOval + mask** | **L** | **Pillow** |
| Glow | `glow.py` | L + mask + analytics | L | Pillow, scipy (optional) |
| Levels | `levels.py` | L + mask + analytics | L | Pillow, numpy |
| **Face Correction** | **`face_correction.py`** | **L + mask + face_mask** | **L + diagnostics** | **numpy, scipy** |
| **Unsharp** | **`unsharp.py`** | **L + mask + analytics** | **L** | **Pillow** |
| **Shadow Noise** | **`shadow_noise.py`** | **L + mask** | **L** | **numpy** |
| **Export** | **`export.py`** | **L** | **BMP/PNG file** | **Pillow, numpy** |
| Vignette | `vignette.py` | L | RGBA | Pillow |

## Конфигурация

Параметры загружаются из `config.yaml` через `retouch/config.py`. Если файл отсутствует — используются встроенные defaults (`DEFAULTS` в config.py).

Приоритет параметров (B.2):
```
UI params (сессия) > order.json (заказ) > config.yaml (базовый) > DEFAULTS
```

Секции конфигурации:
- `processing` — общие параметры (blue_threshold, min_blue_ratio, fringe_radius, face_region_top, highlight_start)
- `processing.laser_standard` / `processing.laser_80w` / `processing.impact` — параметры по типу станка
- `machine` — параметры станка (`step_mm`)
- `stone` — параметры камня (`type`, `heterogeneity`)
- `vignette` — параметры арховой виньетки
- `crm` — связь с granite-crm

См. [reference/config.md](../reference/config.md).

## Связь с granite-crm

Конвенционная связь через поле `crm_company_id` в order.json. Без API-вызовов — ручное связывание.

См. [integration/crm.md](../integration/crm.md).

## Тестирование

266+ автотестов + 31 backend API тест покрывают все модули обработки и Web UI API. Тесты используют синтетические изображения (не требуют реальных фото или GIMP).

```bash
# Запуск всех тестов
make test
# или
python -m pytest tests/ -v
python -m pytest retouch_ui/backend/tests/ -v
```

| Модуль | Файл | Тестов | Что проверяет |
|--------|------|--------|---------------|
| Chromakey | `test_chromakey.py` | 7 | Удаление синего фона, сохранение субъекта, fringe removal, тёмно-синяя одежда |
| Glow | `test_glow.py` | 9 | Laser/impact glow, детерминированный midpoint, яркость контура, opacity, адаптивные параметры |
| Levels | `test_levels.py` | 28 | Brightness, unsharp mask, curves, mask shrink, face brightness, адаптивные Levels/Unsharp, масочная защита |
| **Face Region** | **`test_face_region.py`** | **12** | **Детекция лица (C.1), маска лица (C.2), маска волос, профиль ширины, fallback** |
| Analytics | `test_analysis.py` | 9 | Преданализ: классификация, метрики, масштабная инвариантность, ImageAnalytics dataclass |
| Routing | `test_skill_routing.py` | 5 | machine_type → промпт-файл |
| Vignette | `test_vignette.py` | 7 | RGB выход, чёрные углы, headroom, масштабирование, плавная маска |
| Validation | `test_validation.py` | 20 | Валидация изображения, хромакей, чёрный фон, order.json |
| Config | `test_config.py` | 35 | DEFAULTS структура, диапазоны glow/brightness, загрузка, fallback, deep_merge, machine types |
| Order Schema | `test_order_schema.py` | 26 | Schema integrity, валидные/невалидные заказы, CRM ID, validate_order() |
| Pipeline | `test_pipeline.py` | 18 | Интеграция: laser/impact пайплайн, >25% чёрного, нет пересвета, process_steps/preview/export |
| CLI Integration | `test_cli_integration.py` | 1 | CLI: запуск process через subprocess |
| **Bugfixes A** | **`test_bugfixes_a.py`** | **15** | **A.1 shadow noise в субъекте, A.2 shadow floor, A.3 порядок шагов, A.4 white clamp, A.5 glow rename** |
| **Architecture B** | **`test_architecture_b.py`** | **14** | **B.1 PipelineContext, B.2 трёхуровневый конфиг, B.3 ImageAnalytics dataclass** |
| **Audit Fixes** | **`test_audit_fixes.py`** | **7** | **D.4 Pydantic валидация, D.6 LRU кэш, F.1 расщепление levels** |
| **Quality F** | **`test_quality_f.py`** | **8** | **F.2 метрики качества, F.3 BMP post-save валидация** |
| **Regression G** | **`test_regression_g.py`** | **16** | **G.1 P0 регрессия, G.2 P1 функциональные, G.3 интеграционный** |
| Process API | `test_process_api.py` | 13 | Upload, preview, export, параметры, ошибки |
| Config API | `test_config_api.py` | 5 | GET/PUT /config, /config/defaults |
| Presets API | `test_presets_api.py` | 7 | CRUD пресетов, загрузка YAML |
| Health API | `test_health.py` | 2 | /health endpoint |

Dev-зависимости: `pytest>=7.0`, `jsonschema>=4.0`, `httpx>=0.28.1`. Установка: `uv sync --extra dev`.
