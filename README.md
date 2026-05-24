# granite-retouch — AI-ретушь портретов для гравировки на памятниках

Система автоматизированной подготовки и ретуши портретов для гравировальных станков по камню (габбро/гранит) с использованием мультиагентного ИИ-пайплайна в среде **Google Antigravity IDE**.

Главная проблема отрасли: генеративные нейросети создают «мягкие» изображения, которые плохо гравируются. Система решает это через разделение задач между специализированными ИИ-агентами (Skills) и техническую постобработку.

## Тестирование

```bash
uv sync --extra dev   # pytest + jsonschema
make test              # 460+ тестов + 31 backend API тест
```

## Быстрый старт

```bash
# Создать заказ
uv run python -m retouch order create ORD-2026-042 -m impact

# Обработка портрета (стандартный лазер)
uv run python -m retouch process -i ai.png -o final.bmp -m laser_standard

# Мощный лазер 60-80W+
uv run python -m retouch process -i ai.png -o final.bmp -m laser_80w

# Ударный станок
uv run python -m retouch process -i ai.png -o final.bmp -m impact

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
- Выбор материала (granite, gabbro, marble, acrylic, slate)
- Пресеты по производителю (Mirtels, САУНО, Stanzone, STONE-ГРАФ)
- Экспорт BMP/PNG/TIFF в полном разрешении
- FaceOval overlay — интерактивная коррекция овала лица (перетащить 4 handle)
- **Advanced Mode** — технические параметры скрыты по умолчанию, доступны по чекбоксу
- **Pin Face Oval** — фиксация овала кнопкой-пин, блокировка автообновления при ручном перемещении
- **Просмотр дизеринга** — предпросмотр Jarvis/Stucki дизеринга для всех станков (по кнопке)
- **ParamToggle** — сегментный контрол для glow_style (Outer/Inner) вместо слайдера
- **Profile Selector** — выбор профиля обработки (standard / preserve / diagnostic)

## Конфигурация

Python `DEFAULTS` в `retouch/config.py` — единственный источник истины для
параметров обработки. Frontend `config-defaults.json` генерируется из него
скриптом `scripts/export_defaults.py`. CI проверяет синхронизацию через
`make check-defaults-sync`.

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
| [docs/guides/pipeline-overview.md](docs/guides/pipeline-overview.md) | Как работает пайплайн (без кода) |
| [docs/architecture/pipeline.md](docs/architecture/pipeline.md) | Пайплайн обработки (техническая документация) |
| [docs/architecture/overview.md](docs/architecture/overview.md) | Архитектура проекта, структура каталогов |
| [docs/zones.md](docs/zones.md) | Зональное разделение (ZoneMasks) |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Расшифровка diagnostics warnings |
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
- **Градиентная маска хромакея:** вместо бинарного порога — soft-step вокруг threshold. Плавный контур без зазубрин на диагоналях. Параметр `contour_smooth_epsilon` deprecated (игнорируется)
- **ZoneMasks:** автоматическое зональное разделение (face_skin, face_dark, hair, clothes, highlights) — коррекция применяется только к нужным зонам. Beard detection — переклассификация тёмных зон нижней трети лица в hair
- **Processing profiles:** `standard` (полная обработка), `preserve` (минимальное вмешательство — только chromakey, grayscale, glow, highlight_rolloff, vignette), `diagnostic` (расширенный сбор метрик)
- **Quality gates:** 7 контрольных точек (2 pre-check, 5 post-check) — автоматическое ослабление агрессивных шагов
- **Step metrics:** метрики по зонам после каждого шага — видно какой шаг ухудшил результат
- **Safety Cap:** мягкий rolloff на face_skin перед gamma — предотвращает попадание лица в зону rolloff knee
- **Двухпроходный postprocess:** пробный проход → gate check → ослабление gamma → повторный проход при необходимости

### Processing Profiles

Профиль задаёт набор активных шагов пайплайна. Ортогонален пресету станка
(параметры шагов берутся из пресета, но неподходящие шаги отключаются):

| Profile | Активные шаги | Назначение |
|---------|--------------|------------|
| `preserve` | chromakey, grayscale, glow, highlight_rolloff, vignette | Минимальное вмешательство, почти не меняет исходную AI-ретушь |
| `standard` | chromakey, grayscale, glow, levels, unsharp, shadow_noise, shadow_floor, stone_gamma, white_ceiling, vignette | Полная обработка с автокоррекцией |
| `diagnostic` | Все шаги + расширенные маски и step-метрики | Отладка и анализ качества |

Выбор профиля: через CLI (`--profile preserve`) или UI (Profile Selector).

### Quality Gates

Система pre/post-check gates предотвращает деградацию изображения при агрессивных настройках:

**Pre-check (до шага):**
| Gate | Триггер | Действие |
|------|---------|----------|
| `face_dark_small` | face_dark < 5% от face_mask | Пропустить коррекцию |
| `contour_inner_quality` | контур > 30% субъекта | Fallback на morphological contour |

**Post-check (после шага):**
| Gate | Триггер | Действие |
|------|---------|----------|
| `variance_loss` | потеря variance face_skin > 35% | Ослабить stone_gamma на 50% |
| `clipped_pct` | клиппинг face_skin > 5% | Увеличить rolloff compression на 20% |
| `p95_shift` | сдвиг face_skin p95 > порога (3.0 laser_standard, 5.0 impact) | Ослабить stone_gamma на 50% |
| `p95_shift_cumulative` | cumulative сдвиг face_skin p95 от baseline > порога | Diagnostic only (warning) |
| `shadow_crush` | crush теней > 10% | Отключить shadow_floor и stone_gamma |

Пороги настраиваются через `quality_gates` секцию в config.yaml, включая per-machine переопределения.

Все срабатывания пишутся в `diagnostics` с `gate_name`, `original_value`, `adjusted_value`, `reason`.

### Safety Envelope

Максимальные допустимые дельты коррекции по зонам (настраиваются через `safety_envelope` в config.yaml):

| Зона | Макс. дельта | Обоснование |
|------|-------------|-------------|
| face_skin | ±15 уровней (~6%) | Едва заметно на гравировке |
| face_dark | ±5 уровней | Минимальное вмешательство (брови, тени) |
| hair | ±3 уровня | Почти не трогаем |
| clothes | 0 | Одежда не меняется по решению лица |

### Rolling Ceiling

Вместо hard clamp `np.clip()` используется `soft_rolloff_masked()`:

- **Принцип:** Плавное сжатие light-зоны после порога knee, а не обрезание
- **Формула:** `output = knee + max(value - knee, 0) * (1 - compression)`
- **По зонам (v6.5):** Rolloff применяется к `highlights` и `face_skin` (не ко всему subject)
- **Параметры:** `rolloff_knee` (по умолч. 90% от white_ceiling), `rolloff_compression` (по умолч. 0.35) из config.yaml

## Known Limitations

### Preview ≠ Export: детекция лица и параметры

Предпросмотр (Web UI) и экспорт (CLI/API) обрабатывают изображения на разных разрешениях, что может приводить к расхождениям в результатах:

- **Размер изображения:** Preview уменьшает до 768px по длинной стороне, экспорт работает с полным разрешением. Это влияет на адаптивные параметры, которые зависят от размера (glow, face detection kernel).
- **Детекция лица:** Эвристика по профилю ширины маски использует скользящее среднее с kernel, пропорциональным высоте. При разной высоте сглаженный профиль отличается → позиция овала лица может смещаться на 1-5% между preview и export.
- **Glow:** В preview glow фиксируется на середине диапазона (deterministic), в экспорте — адаптивный расчёт. Поэтому preview-результат может отличаться от финального.
- **Рекомендация:** Для точного контроля позиции лица используйте FaceOval overlay в Web UI — заданный овал передаётся и в preview, и в export без изменений.

### Deprecated поле `brightness` → `stone_gamma`

Конфигурация использует `stone_gamma` (SOP 5.1) вместо устаревшего `brightness`. Если в `config.yaml` или через UI передан `brightness`, он автоматически мигрируется в `stone_gamma` с DeprecationWarning. Рекомендуется обновить конфигурацию вручную.

### Deprecated поле `stone.type` → `stone.material`

Конфигурация использует `material` вместо устаревшего `stone.type`. Оба ключа синхронизируются автоматически — `material` является источником истины. `stone.type` будет удалён в v5.

### Градиентная маска хромакея

Контур вырезки хромакея — градиентная маска (soft-step вокруг threshold) вместо бинарного порога. Плавный контур без зазубрин на диагоналях. Параметр `contour_smooth_epsilon` deprecated (игнорируется). Ветка `if HAS_CV2:` убрана — один путь кода для всех окружений.
