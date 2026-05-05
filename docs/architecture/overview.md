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
│   │   ├── glow.py              # Inner Glow (contour light)
│   │   ├── levels.py            # Levels + Brightness + Unsharp + face brightness
│   │   ├── vignette.py          # Арховая виньетка
│   │   └── pipeline.py          # Полный пайплайн (оркестратор)
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
│   ├── backend/                 # FastAPI sidecar (localhost:8001)
│   │   ├── main.py              # App + lifespan + CORS + StaticFiles
│   │   ├── schemas.py           # Pydantic-модели запросов/ответов
│   │   ├── routers/
│   │   │   ├── process.py       # /upload, /process/preview, /process/export
│   │   │   ├── config.py        # GET/PUT /config, /config/defaults
│   │   │   └── presets.py       # GET/POST/DELETE /presets
│   │   └── tests/               # Backend API тесты
│   └── frontend/                # React + Vite
│       ├── src/                 # Компоненты, хуки, API-клиент
│       └── dist/                # Production-сборка (gitignore)
├── presets/                     # YAML-пресеты (laser-default, impact-soft, ...)
├── tests/                       # Автотесты (~158 тестов)
│   ├── conftest.py              # Фикстуры: синтетические PNG с хромакеем
│   ├── test_chromakey.py        # Удаление синего фона, fringe, одежда
│   ├── test_glow.py             # Laser/impact glow размеры и opacity
│   ├── test_levels.py           # Brightness, unsharp, curves, face brightness
│   ├── test_vignette.py         # Арховая виньетка, масштабирование
│   ├── test_validation.py       # Валидация изображения и order.json
│   ├── test_config.py           # Загрузка конфига, defaults, fallback
│   ├── test_order_schema.py     # JSON Schema: валидные/невалидные заказы
│   ├── test_pipeline.py         # Интеграция: полный пайплайн
│   └── test_cli_integration.py  # CLI: интеграционный тест
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
                 [retouch process] ──→ final.tiff + final.png (чёрный фон)
```

## Модули обработки

| Модуль | Файл | Вход | Выход | Зависимости |
|--------|------|------|-------|-------------|
| Chromakey | `chromakey.py` | RGBA | RGBA + mask (L) | numpy, scipy |
| Inner Glow | `glow.py` | L + mask | L | Pillow |
| Levels | `levels.py` | L | L | Pillow, numpy |
| Face Brightness | `levels.py` | L + mask | L | numpy, scipy |
| Vignette | `vignette.py` | L + mask | RGBA | Pillow |

## Конфигурация

Параметры загружаются из `config.yaml` через `retouch/config.py`. Если файл отсутствует — используются встроенные defaults (`DEFAULTS` в config.py).

Приоритет: `--config` аргумент > `config.yaml` в корне проекта > `config.yaml` в CWD > DEFAULTS.

См. [reference/config.md](../reference/config.md).

## Связь с granite-crm

Конвенционная связь через поле `crm_company_id` в order.json. Без API-вызовов — ручное связывание.

См. [integration/crm.md](../integration/crm.md).

## Тестирование

~158 автотестов покрывают все модули обработки и Web UI API. Тесты используют синтетические изображения (не требуют реальных фото или GIMP).

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
| Inner Glow | `test_glow.py` | 6 | Laser/impact glow размеры, яркость контура, random range, opacity |
| Levels | `test_levels.py` | 16 | Brightness, unsharp mask, curves, mask shrink, face brightness |
| Vignette | `test_vignette.py` | 7 | RGB выход, чёрные углы, headroom, масштабирование, плавная маска |
| Validation | `test_validation.py` | 20 | Валидация изображения, хромакей, чёрный фон, order.json |
| Config | `test_config.py` | 30 | DEFAULTS структура, диапазоны glow/brightness, загрузка, fallback, deep_merge |
| Order Schema | `test_order_schema.py` | 26 | Schema integrity, валидные/невалидные заказы, CRM ID, validate_order() |
| Pipeline | `test_pipeline.py` | 18 | Интеграция: laser/impact пайплайн, >25% чёрного, нет пересвета, process_steps/preview/export |
| CLI Integration | `test_cli_integration.py` | 1 | CLI: запуск process через subprocess |
| Process API | `test_process_api.py` | 13 | Upload, preview, export, параметры, ошибки |
| Config API | `test_config_api.py` | 5 | GET/PUT /config, /config/defaults |
| Presets API | `test_presets_api.py` | 7 | CRUD пресетов, загрузка YAML |
| Health API | `test_health.py` | 2 | /health endpoint |

Dev-зависимости: `pytest>=7.0`, `jsonschema>=4.0`, `httpx>=0.28.1`. Установка: `uv pip install -e ".[dev]"`.
