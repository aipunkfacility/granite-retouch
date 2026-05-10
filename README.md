# granite-retouch — AI-ретушь портретов для гравировки на памятниках

Система автоматизированной подготовки и ретуши портретов для гравировальных станков по камню (габбро/гранит) с использованием мультиагентного ИИ-пайплайна в среде **Google Antigravity IDE**.

Главная проблема отрасли: генеративные нейросети создают «мягкие» изображения, которые плохо гравируются. Система решает это через разделение задач между специализированными ИИ-агентами (Skills) и техническую постобработку.

## Тестирование

```bash
uv sync --extra dev   # pytest + jsonschema
make test                     # 266+ тестов + 31 backend API тест
```

## Быстрый старт

```bash
# Создать заказ
uv run python -m retouch order create ORD-2026-042 -m impact

# Обработка портрета (стандартный лазер)
uv run python -m retouch process -i ai.png -o final.bmp -m laser_standard

# Мощный лазер 60-80W+
uv run python -m retouch process -i ai.png -o final.bmp -m laser_80w

# Список заказов
uv run python -m retouch order list
```

См. [docs/getting-started.md](docs/getting-started.md) — полный цикл за 5 шагов.

## Web UI

Интерактивная настройка параметров с живым предпросмотром:

```bash
make ui          # dev-режим: backend + frontend (порты 8000 и 5173)
make ui-prod     # production: один процесс uvicorn, статику раздаёт FastAPI
```

Возможности:
- Загрузка изображения через drag & drop
- Живой предпросмотр при изменении параметров (слайдеры)
- Переключение станка laser_standard / laser_80w / impact
- Пресеты (готовые наборы параметров из `presets/`)
- Экспорт BMP/PNG/TIFF в полном разрешении
- FaceOval overlay — интерактивная коррекция овала лица (перетащить 4 handle)

## Документация

Полная документация в `docs/`. См. [docs/index.md](docs/index.md).

| Документ | Описание |
|----------|----------|
| [docs/getting-started.md](docs/getting-started.md) | Быстрый старт (5 шагов) |
| [docs/reference/cli.md](docs/reference/cli.md) | Справочник всех CLI-команд |
| [docs/reference/config.md](docs/reference/config.md) | Все параметры config.yaml |
| [docs/guides/vignette.md](docs/guides/vignette.md) | Арховая виньетка |
| [docs/guides/style-guide-laser.md](docs/guides/style-guide-laser.md) | Стиль лазерной генерации (20-40W) |
| [docs/guides/style-guide-laser-80w.md](docs/guides/style-guide-laser-80w.md) | Стиль генерации для мощных лазеров (60-80W+) |
| [docs/guides/style-guide-impact.md](docs/guides/style-guide-impact.md) | Стиль ударной генерации |
| [docs/architecture/pipeline.md](docs/architecture/pipeline.md) | Пайплайн обработки |
| [docs/integration/crm.md](docs/integration/crm.md) | Интеграция с granite-crm |

## Агентная архитектура

Процесс проходит через следующих агентов:

1. **[Analyzer Agent](.agents/skills/retouch-analyzer/SKILL.md)** — анализирует фото, заполняет профиль заказа
2. **[Prompter Agent](.agents/skills/retouch-prompter/SKILL.md)** — собирает промпт из атомарных блоков
3. **Generation Step (Manual)** — оператор генерирует в Nano Banana на синем хромакее (`#0000FF`)
4. **[Post-Processing](.agents/skills/retouch-postprocessing/CHECKLIST.md)** — техническая подготовка файла (CLI или Photoshop)

## Базовые принципы

- **Синий хромакей:** Все генерации на фоне `Solid Deep Blue (#0000FF)` для чистой вырезки
- **Идентичность:** Строгий запрет на изменение геометрии лица
- **Разделение текстур:** Гладкое лицо для объёма + сверхрезкая одежда для станка
- **Адаптивный pipeline:** Преданализ (13 метрик, ImageAnalytics dataclass) + масочная защита — коррекция только внутри маски субъекта
- **Детекция лица:** трёхуровневая стратегия (профиль ширины маски → ручной овал → mediapipe в будущем)
- **PipelineContext:** внутренняя упаковка параметров для уменьшения связности между шагами пайплайна
