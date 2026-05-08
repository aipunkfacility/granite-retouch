# Документация granite-retouch

Карта проектной документации. Каждый документ покрывает одну тему — можно читать выборочно.

---

## Быстрый старт

- **[getting-started.md](getting-started.md)** — 5 шагов от заказа до готового файла

## Справочники

Ищут конкретную команду, параметр или формат.

- **[reference/cli.md](reference/cli.md)** — все команды `retouch` CLI (process, validate, gimp, order)
- **[reference/config.md](reference/config.md)** — все параметры config.yaml с диапазонами и значениями по умолчанию
- **[reference/order-schema.md](reference/order-schema.md)** — поля order.json, типы, примеры

## Пошаговые руководства

Читают последовательно для понимания конкретного аспекта.

- **[guides/vignette.md](guides/vignette.md)** — арховая виньетка: параметры, формулы, пресеты, диагностика
- **[guides/style-guide-laser.md](guides/style-guide-laser.md)** — стиль генерации для лазерной гравировки (20–40W)
- **[guides/style-guide-laser-80w.md](guides/style-guide-laser-80w.md)** — стиль генерации для мощных лазеров (60–80W+)
- **[guides/style-guide-impact.md](guides/style-guide-impact.md)** — стиль генерации для ударной гравировки
- **[guides/nano-banana.md](guides/nano-banana.md)** — работа с Nano Banana Pro

## Архитектура

Для разработчиков и отладки.

- **[architecture/overview.md](architecture/overview.md)** — структура проекта, модули, потоки данных, тестирование
- **[architecture/pipeline.md](architecture/pipeline.md)** — пайплайн обработки: chromakey → analytics → face detection → glow → levels → face brightness → unsharp → shadow noise/floor → vignette → export
- **Face Pipeline** — детекция лица (C.1) → маска лица/волос (C.2) → интеграция в пайплайн (C.3). См. [architecture/pipeline.md](architecture/pipeline.md#4b-детекция-зоны-лица-c1)
- **Export Reference** — BMP 8-bit/1-bit, Floyd-Steinberg дизеринг, post-validation (F.3). См. [architecture/pipeline.md](architecture/pipeline.md#11-сохранение-bmppng)

## Тестирование

266+ автотестов + 31 backend API тест покрывают все модули. Запуск: `make test` или `pytest tests/ -v`. Подробнее в [architecture/overview.md](architecture/overview.md#тестирование).

## Интеграции

- **[integration/crm.md](integration/crm.md)** — связь с granite-crm через crm_company_id

---

## Для ИИ-агентов (Antigravity Skills)

Агенты используют отдельные файлы навыков, не эту документацию:

- `.agents/skills/retouch-analyzer/SKILL.md` — анализ фото
- `.agents/skills/retouch-prompter/SKILL.md` — сборка промпта
- `.agents/skills/retouch-postprocessing/CHECKLIST.md` — чек-лист Photoshop

## База знаний

- `knowledge/principles.md` — фундаментальные принципы (синий фон, резкость, идентичность)
- `knowledge/machines/laser.md` — специфика лазерных станков
- `knowledge/machines/impact.md` — специфика ударных станков
