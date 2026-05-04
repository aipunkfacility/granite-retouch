# granite-retouch — AI-ретушь портретов для гравировки на памятниках

Система автоматизированной подготовки и ретуши портретов для гравировальных станков по камню (габбро/гранит) с использованием мультиагентного ИИ-пайплайна в среде **Google Antigravity IDE**.

Главная проблема отрасли: генеративные нейросети создают «мягкие» изображения, которые плохо гравируются. Система решает это через разделение задач между специализированными ИИ-агентами (Skills) и техническую постобработку.

## Тестирование

```bash
uv pip install -e ".[dev]"   # pytest + jsonschema
make test                     # 98 тестов
```

## Быстрый старт

```bash
# Создать заказ
python -m retouch order create ORD-2026-042 -m impact

# Обработка портрета
python -m retouch process -i ai.png -o final.tiff -m laser

# Список заказов
python -m retouch order list
```

См. [docs/getting-started.md](docs/getting-started.md) — полный цикл за 5 шагов.

## Документация

Полная документация в `docs/`. См. [docs/index.md](docs/index.md).

| Документ | Описание |
|----------|----------|
| [docs/getting-started.md](docs/getting-started.md) | Быстрый старт (5 шагов) |
| [docs/reference/cli.md](docs/reference/cli.md) | Справочник всех CLI-команд |
| [docs/reference/config.md](docs/reference/config.md) | Все параметры config.yaml |
| [docs/guides/vignette.md](docs/guides/vignette.md) | Арховая виньетка |
| [docs/guides/style-guide-laser.md](docs/guides/style-guide-laser.md) | Стиль лазерной генерации |
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
