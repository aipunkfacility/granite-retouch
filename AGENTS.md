# AGENTS.md — Навигатор для ИИ-агентов

## Обзор

granite-retouch — система автоматизации подготовки промптов для генерации портретов, предназначенных для гравировки на станках по камню (габбро/гранит).

**Важно:** Агенты генерируют только текстовые промпты для Nano Banana, а не изображения напрямую. Генерация выполняется оператором вручную.

## Документация

Полная документация в `docs/`. См. [docs/index.md](docs/index.md).

Ключевые документы:
- [docs/getting-started.md](docs/getting-started.md) — 5 шагов от заказа до файла
- [docs/reference/cli.md](docs/reference/cli.md) — все команды `retouch` CLI
- [docs/reference/config.md](docs/reference/config.md) — все параметры config.yaml
- [docs/architecture/pipeline.md](docs/architecture/pipeline.md) — пайплайн обработки

## ИИ-агенты (Antigravity Skills)

| Агент | SKILL.md | Назначение |
|-------|----------|------------|
| retouch-analyzer | `.agents/skills/retouch-analyzer/SKILL.md` | Анализ фото → `analyzer_output` в order.json |
| retouch-prompter | `.agents/skills/retouch-prompter/SKILL.md` | Сборка промпта из блоков → `prompt.md` |
| retouch-postprocessing | `.agents/skills/retouch-postprocessing/CHECKLIST.md` | Чек-лист Photoshop |

## Быстрые команды

```bash
# Обработка портрета
uv run python -m retouch process -i ai.png -o final.bmp -m laser_standard

# Управление заказами
uv run python -m retouch order create ORD-2026-042 --crm CMP-0042 -m impact
uv run python -m retouch order list
uv run python -m retouch order validate ORD-2026-042

# Тесты (132+ автотестов, не требуют GIMP/фото)
make test

# Web UI — интерактивная настройка с предпросмотром
make ui              # dev-режим: backend + frontend (два процесса)
make ui-backend      # только FastAPI backend
make ui-frontend     # только Vite frontend
make ui-prod         # production: статики + uvicorn (один процесс)
```

## Соглашения об именовании

### Order ID

Формат: `ORD-YYYY-NNN` (напр. `ORD-2026-042`).

### CRM Company ID

Формат: `CMP-NNNN` (напр. `CMP-0042`).

### Папки заказов

```
orders/active/ORD-2026-001/
├── order.json           # Данные заказа
├── prompt.md            # Промпт для копирования
└── generated/
    ├── source.jpg       # Исходное фото
    ├── ai.png           # Нейро-ретушь (синий фон)
    ├── final.tiff       # Готовый файл (чёрный фон)
    └── final.png        # Превью
```

## Стиль кода

### Markdown

- Длина строки: 100 символов максимум
- Язык: русский (предпочтительно для документации)
- Заголовки: иерархия h1 → h2 → h3, один h1 на файл
- Списки: маркированные с дефисом, вложенные — 2 пробела отступа

### JSON

- Отступ: 2 пробела
- Кавычки: двойные всегда
- Кодировка: UTF-8
- Именование ключей: camelCase

## Обработка ошибок

- Всегда проверять JSON по схеме `orders/schema.json`
- Обязательные поля: `order_id`, `machine_type`, `source_photo`, `status`
- Тип станка: `laser_standard`, `laser_80w` или `impact`
- При валидации изображения: `ValidationError` + понятное сообщение

---

Обновлено: 2026-05-07
