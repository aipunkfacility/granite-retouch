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
├── docs/                        # Документация
├── config.yaml                  # Параметры обработки
├── pyproject.toml               # Пакетная конфигурация
├── Makefile                     # Шорткаты
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
