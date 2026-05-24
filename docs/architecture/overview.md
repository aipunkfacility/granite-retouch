# Архитектура проекта

## Структура каталогов

```
granite-retouch/
├── retouch/                     # Python-пакет (ядро)
│   ├── __init__.py
│   ├── __main__.py              # python -m retouch
│   ├── cli.py                   # CLI: process, validate, gimp, order
│   ├── config.py                # Загрузка config.yaml + DEFAULTS + миграции v0→v4
│   ├── presets_catalog.py       # Реестр пресетов для UI
│   ├── processing/
│   │   ├── core/                # Оркестрация пайплайна
│   │   │   ├── pipeline.py      # process_steps/preview/export + PipelineContext
│   │   │   ├── steps.py         # run_pipeline_steps — выполнение шагов
│   │   │   ├── context.py       # PipelineContext + PipelineResult dataclass
│   │   │   ├── plan.py          # PipelinePlan, SafetyEnvelope, ValidatedPlan
│   │   │   ├── gates.py         # 7 quality gates (2 pre-check, 5 post-check)
│   │   │   └── gates_enforcement.py  # enforce_gates — ослабление параметров
│   │   ├── detection/           # Детекция и выделение объектов
│   │   │   ├── chromakey.py     # Градиентная маска хромакея + fringe removal
│   │   │   └── face_region.py   # Детекция овала лица (C.1) + генерация масок (C.2)
│   │   ├── analysis/            # Аналитика и метрики
│   │   │   ├── analysis.py      # Преданализ: 13 метрик + ImageAnalytics dataclass
│   │   │   ├── zones.py         # ZoneMasks — зональное разделение + приоритизация
│   │   │   └── metrics.py       # ZoneMetrics + StepMetricsRecord — метрики по зонам
│   │   ├── correction/          # Коррекция изображения
│   │   │   ├── glow.py          # Glow: inner (A.5) + outer + адаптивные параметры
│   │   │   ├── levels.py        # Levels (bounded delta) — legacy re-exports
│   │   │   ├── face_brightness.py  # face_brightness_correction() + curves
│   │   │   ├── unsharp.py       # apply_unsharp_mask() + адаптивный percent
│   │   │   ├── gamma.py         # apply_stone_gamma_masked() — гамма-коррекция
│   │   │   ├── shadow_noise.py  # add_shadow_noise() — шум в тенях для impact
│   │   │   ├── postprocess.py   # shadow_floor + stone_gamma + white_ceiling + rolloff
│   │   │   ├── rolloff.py       # soft_rolloff_masked() — унифицированный soft knee
│   │   │   └── mask_utils.py    # clamp_masked() — масочная защита
│   │   └── output/              # Финальная обработка и экспорт
│   │       ├── vignette.py      # Арховая виньетка
│   │       └── export.py        # BMP/PNG экспорт + Jarvis/Stucki дизеринг
│   ├── gimp/
│   │   └── runner.py            # Поиск и запуск GIMP (experimental)
│   ├── validation/
│   │   ├── image.py             # Валидация входного изображения
│   │   └── order.py             # Валидация order.json по schema.json
│   └── debug/
│       └── pixel_report.py      # Отладочный отчёт по пикселям
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
│   │   ├── schemas.py           # Pydantic-модели запросов/ответов
│   │   ├── routers/
│   │   │   ├── process.py       # /upload, /process/preview, /process/export, /dither-preview
│   │   │   ├── config.py        # GET/PUT /config, /config/defaults
│   │   │   ├── presets.py       # GET/POST/DELETE /presets, /presets/catalog
│   │   │   └── material.py      # /material/profiles, /material/validate
│   │   └── tests/               # Backend API тесты (31 тест)
│   └── frontend/                # React + Vite
│       ├── src/                 # Компоненты, хуки, overlays
│       │   ├── hooks/           # use-preview, use-config, use-preset-material, etc.
│       │   ├── components/      # params-panel, step-selector, face-oval-overlay, etc.
│       │   └── lib/             # types, config-schema, machine-theme, utils
│       └── dist/                # Production-сборка (gitignore)
├── presets/                     # YAML-пресеты (laser-default, impact-default, по производителям)
├── scripts/                     # Скрипты утилит
│   ├── export_defaults.py       # Экспорт DEFAULTS → config-defaults.json
│   ├── generate_dither_fixtures.py  # Регенерация эталонов дизеринга
│   └── analyze_ai_brightness.py # Анализ яркости AI-ретушей
├── tests/                       # Автотесты (460+ тестов)
│   ├── conftest.py              # Фикстуры + sample_pipeline_context
│   ├── test_chromakey.py        # 20 тестов
│   ├── test_glow.py             # 9 тестов
│   ├── test_levels.py           # 28 тестов
│   ├── test_face_region.py      # 12 тестов — C.1 детекция, C.2 маски
│   ├── test_analysis.py         # 9 тестов
│   ├── test_vignette.py         # 7 тестов
│   ├── test_validation.py       # 20 тестов
│   ├── test_config.py           # 35 тестов
│   ├── test_order_schema.py     # 26 тестов
│   ├── test_pipeline.py         # 18 тестов
│   ├── test_cli_integration.py  # 1 тест
│   ├── test_bugfixes_a.py       # 15 тестов — A.1–A.5 регрессия
│   ├── test_api.py              # 7 тестов
│   ├── test_quality_gates.py    # тесты quality gates
│   ├── test_pipeline_gates_enforcement.py  # тесты enforce_gates
│   ├── test_pipeline_with_gates.py         # интеграция gates + pipeline
│   ├── test_pipeline_context.py            # PipelineContext тесты
│   ├── test_pipeline_plan.py               # PipelinePlan тесты
│   ├── test_step_metrics.py                # StepMetrics тесты
│   ├── test_zonal_correction.py            # зональная коррекция
│   ├── test_zone_masks.py                  # ZoneMasks тесты
│   ├── test_presets_validation.py          # валидация пресетов
│   ├── test_material_overrides.py          # MATERIAL_PROFILES тесты
│   ├── test_config_migration.py            # миграции конфига
│   ├── test_face_brightness.py             # face_brightness_correction
│   ├── test_face_brightness_delta.py       # face brightness delta
│   ├── test_soft_rolloff.py                # soft_rolloff_masked
│   ├── test_gamma.py                       # stone_gamma
│   ├── test_export.py                      # BMP/PNG экспорт
│   ├── test_dither_regression.py           # регрессия дизеринга
│   ├── test_imports.py                     # проверка импортов
│   ├── test_memory.py                      # утечки памяти
│   ├── test_safety_envelope.py             # SafetyEnvelope
│   ├── test_chromakey.py                   # хромакей
│   ├── test_glow_algorithms.py             # glow алгоритмы
│   ├── test_p2_integration.py              # P2 интеграция
│   ├── test_preview_export_consistency.py  # consistency preview/export
│   └── test_gimp_runner.py                 # GIMP runner
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
                              [ZoneMasks] → face_skin, face_dark, hair, clothes, highlights
                                          ↓
                              [Glow ← analytics, детерминировано (D.1)] →
                              [Face Brightness Correction ← face_skin_mask, bounded delta] →
                              [Unsharp ← analytics + face_skin overshoot limit] →
                              [Safety Cap ← face_skin soft rolloff before gamma] →
                              [Shadow Noise (impact only)] →
                              [Postprocess: shadow_floor + stone_gamma + white_ceiling + rolloff]
                                (2-pass: пробный → gate check → ослабление gamma → повтор) →
                              [Vignette] → [Export BMP + Post-Validation]
                                               ↓
                                 final.bmp + final.png (чёрный фон)
```

## Модули обработки

| Модуль | Файл | Вход | Выход | Зависимости |
|--------|------|------|-------|-------------|
| Chromakey | `detection/chromakey.py` | RGBA | RGBA + gradient mask (L) | numpy, scipy |
| Analytics | `analysis/analysis.py` | L + mask | ImageAnalytics (dataclass) | numpy |
| Face Detection | `detection/face_region.py` | L + mask | FaceOval (dict) | numpy |
| Face Mask | `detection/face_region.py` | FaceOval + mask | L | Pillow |
| ZoneMasks | `analysis/zones.py` | masks + L | ZoneMasks (dataclass) | numpy, scipy |
| Glow | `correction/glow.py` | L + mask + analytics | L | Pillow, scipy (optional) |
| Face Brightness | `correction/face_brightness.py` | L + mask + face_skin_mask | L + diagnostics | numpy, scipy |
| Unsharp | `correction/unsharp.py` | L + mask + analytics | L | Pillow |
| Shadow Noise | `correction/shadow_noise.py` | L + mask | L | numpy |
| Gamma | `correction/gamma.py` | L + mask | L | numpy |
| Postprocess | `correction/postprocess.py` | L + masks + zone_masks | L | numpy |
| Soft Rolloff | `correction/rolloff.py` | arr + mask + params | arr | numpy |
| Export | `output/export.py` | L | BMP/PNG file | Pillow, numpy |
| Vignette | `output/vignette.py` | L | RGBA | Pillow |

## Модули принятия решений

| Модуль | Файл | Назначение |
|--------|------|------------|
| PipelinePlan | `core/plan.py` | Описание плана: профиль → активные шаги + параметры |
| SafetyEnvelope | `core/plan.py` | Максимальные допустимые дельты по зонам (face_skin ±15, face_dark ±5, hair ±3, clothes 0) |
| ValidatedPlan | `core/plan.py` | План после валидации: отключённые шаги, клипнутые параметры, warnings |
| Quality Gates | `core/gates.py` | 7 контрольных точек (2 pre-check, 5 post-check) — GateResult dataclass |
| Gates Enforcement | `core/gates_enforcement.py` | Ослабление параметров: shadow_crush → сброс, variance_loss/p95_shift → gamma ×0.5, clipped_pct → compression ×1.2 |
| PipelineContext | `core/context.py` | Внутренняя упаковка параметров между шагами |
| PipelineResult | `core/context.py` | Результат: промежуточные изображения + диагностика + метрики + gate_state |

## Конфигурация

Параметры загружаются из `config.yaml` через `retouch/config.py`. Если файл отсутствует — используются встроенные defaults (`DEFAULTS` в config.py).

Приоритет параметров (B.2):
```
UI params (сессия) > order.json (заказ) > config.yaml (базовый) > DEFAULTS
```

Секции конфигурации:
- `processing` — общие параметры (blue_threshold, min_blue_ratio, fringe_radius, face_oval_enabled, quality_gates)
- `processing.laser_standard` / `processing.laser_80w` / `processing.impact` — параметры по типу станка
- `machine` — параметры станка (`step_mm` — глобальный fallback, переопределяется per-machine)
- `stone` — параметры камня (`material`, `type` deprecated, `heterogeneity`)
- `safety_envelope` — максимальные дельты коррекции по зонам
- `vignette` — параметры арховой виньетки
- `crm` — связь с granite-crm

Материалы (MATERIAL_PROFILES): granite, gabbro, basalt, marble, acrylic, slate — с автокоррекцией step_mm, stone_gamma, shadow_floor, export_mode.

См. [reference/config.md](../reference/config.md).

## Связь с granite-crm

Конвенционная связь через поле `crm_company_id` в order.json. Без API-вызовов — ручное связывание.

См. [integration/crm.md](../integration/crm.md).

## Тестирование

460+ автотестов + 31 backend API тест покрывают все модули обработки и Web UI API. Тесты используют синтетические изображения (не требуют реальных фото или GIMP).

```bash
# Запуск всех тестов
make test
# или
python -m pytest tests/ -v
python -m pytest retouch_ui/backend/tests/ -v
```

| Модуль | Файл | Что проверяет |
|--------|------|---------------|
| Chromakey | `test_chromakey.py` | Удаление синего фона, антиалиасный контур, софт-маска, fringe removal, тёмно-синяя одежда |
| Glow | `test_glow.py` | Laser/impact glow, детерминированный midpoint, яркость контура, opacity, адаптивные параметры |
| Levels | `test_levels.py` | Brightness, unsharp mask, curves, mask shrink, face brightness, адаптивные Levels/Unsharp, масочная защита |
| Face Region | `test_face_region.py` | Детекция лица (C.1), маска лица (C.2), маска волос, профиль ширины, fallback |
| Analytics | `test_analysis.py` | Преданализ: классификация, метрики, масштабная инвариантность, ImageAnalytics dataclass |
| Zone Masks | `test_zone_masks.py` | ZoneMasks: построение, приоритизация, beard detection, адаптивный порог кожи |
| Pipeline Plan | `test_pipeline_plan.py` | PipelinePlan, SafetyEnvelope, ValidatedPlan, профиль active_steps |
| Quality Gates | `test_quality_gates.py` | Pre-check и post-check gates, GateResult, GateState |
| Gates Enforcement | `test_pipeline_gates_enforcement.py` | enforce_gates: ослабление gamma, сброс shadow_floor, compression |
| Pipeline Context | `test_pipeline_context.py` | PipelineContext, PipelineResult, release_intermediates, consistency check |
| Step Metrics | `test_step_metrics.py` | ZoneMetrics, StepMetricsRecord, compute_zone_metrics |
| Zonal Correction | `test_zonal_correction.py` | Коррекция по зонам, face_skin delta |
| Safety Envelope | `test_safety_envelope.py` | SafetyEnvelope.from_config, limits |
| Soft Rolloff | `test_soft_rolloff.py` | soft_rolloff_masked, build_face_safe_rolloff_mask |
| Face Brightness | `test_face_brightness.py` | face_brightness_correction, curves, face_skin_mask |
| Shadow Noise | `test_shadow_noise.py` / `test_shadow_noise_invariants.py` | Шум только в субъекте (A.1), параметры |
| Gamma | `test_gamma.py` | apply_stone_gamma_masked, диапазоны |
| Export | `test_export.py` | BMP 8-bit/1-bit, DPI, дизеринг, post-validation |
| Config | `test_config.py` | DEFAULTS структура, диапазоны, загрузка, fallback, deep_merge, machine types, миграции |
| Config Migration | `test_config_migration.py` | v0→v4 миграции, идемпотентность |
| Config Defaults Sync | `test_config_defaults_sync.py` / `test_config_defaults_json.py` | Синхронизация DEFAULTS ↔ config-defaults.json |
| Order Schema | `test_order_schema.py` | Schema integrity, валидные/невалидные заказы, CRM ID |
| Pipeline | `test_pipeline.py` | Интеграция: laser/impact пайплайн, >25% чёрного, нет пересвета |
| Pipeline with Gates | `test_pipeline_with_gates.py` | Интеграция gates + pipeline, двухпроходный postprocess |
| Bugfixes A | `test_bugfixes_a.py` | A.1 shadow noise в субъекте, A.2 shadow floor, A.3 порядок шагов, A.4 white clamp, A.5 glow rename |
| Presets | `test_presets_validation.py` | Валидация пресетов, загрузка YAML |
| Material Overrides | `test_material_overrides.py` | MATERIAL_PROFILES, apply_material_overrides, validate_machine_material |
| Preview/Export Consistency | `test_preview_export_consistency.py` | Расхождение preview ↔ export |
| P2 Integration | `test_p2_integration.py` | P2 адаптивный Levels интеграция |
| Dither Regression | `test_dither_regression.py` | Регрессия дизеринга на эталонах |
| Memory | `test_memory.py` | Утечки памяти, release_intermediates |
| CLI Integration | `test_cli_integration.py` | CLI: запуск process через subprocess |
| Process API | `test_process_api.py` | Upload, preview, export, параметры, ошибки |
| Config API | `test_config_api.py` | GET/PUT /config, /config/defaults |
| Presets API | `test_presets_api.py` | CRUD пресетов, загрузка YAML |
| Health API | `test_health.py` | /health endpoint |

Dev-зависимости: `pytest>=7.0`, `jsonschema>=4.0`, `httpx>=0.28.1`. Установка: `uv sync --extra dev`.
