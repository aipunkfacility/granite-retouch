# granite-retouch — AI-ретушь портретов для гравировки на памятниках

Система автоматизированной подготовки и ретуши портретов для гравировальных станков по камню (габбро/гранит) с использованием мультиагентного ИИ-пайплайна в среде **Google Antigravity IDE**.

Главная проблема отрасли: генеративные нейросети создают «мягкие» изображения, которые плохо гравируются. Система решает это через разделение задач между специализированными ИИ-агентами (Skills) и техническую постобработку.

## Тестирование

```bash
uv sync --extra dev   # pytest + jsonschema
make test                     # 451+ тестов + 31 backend API тест
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
- **Advanced Mode** — технические параметры скрыты по умолчанию, доступны по чекбоксу
- **Pin Face Oval** — фиксация овала кнопкой-пин, блокировка автообновления при ручном перемещении
- **Просмотр дизеринга** — предпросмотр Jarvis дизеринга для laser_80w (по кнопке)
- **ParamToggle** — сегментный контрол для glow_style (Outer/Inner) вместо слайдера

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
- **Антиалиасный контур:** векторная трассировка через OpenCV (`cv2.LINE_AA`) — гладкий контур хромакея без лесенки на диагоналях. Без cv2 — fallback на GaussianBlur
- **ZoneMasks:** автоматическое зональное разделение (face_skin, face_dark, hair, clothes, highlights) — коррекция применяется только к нужным зонам
- **Processing profiles:** `standard` (полная обработка), `preserve` (минимальное вмешательство), `diagnostic` (расширенный сбор метрик)
- **Quality gates:** 7 контрольных точек (3 pre-check, 4 post-check) — автоматическое ослабление агрессивных шагов
- **Step metrics:** метрики по зонам после каждого шага — видно какой шаг ухудшил результат

### Quality Gates

Система pre/post-check gates предотвращает деградацию изображения при агрессивных настройках:

**Pre-check (до шага):**
| Gate | Триггер | Действие |
|------|---------|----------|
| `face_dark_small` | < 5% тёмных пикселей лица | Пропустить коррекцию |
| `contour_inner_quality` | контур > 30% субъекта | Fallback на morphological contour |
| `skin_delta_envelope` | delta > safety envelope | Клиппинг до ±max_delta |

**Post-check (после шага):**
| Gate | Триггер | Действие |
|------|---------|----------|
| `variance_loss` | потеря variance > 35% | Ослабить stone_gamma на 50% |
| `clipped_pct` | клиппинг > 5% | Увеличить rolloff compression на 20% |
| `p95_shift` | сдвиг p95 > 20 | Ослабить skin_delta на 50% |
| `shadow_crush` | crush теней > 10% | Отключить shadow_floor и stone_gamma |

Все срабатывания пишутся в `diagnostics` с `gate_name`, `original_value`, `adjusted_value`, `reason`.

### Rolling Ceiling

Вместо hard clamp `np.clip()` используется `soft_rolloff_masked()`:

- **Принцип:** Плавное сжатие light-зоны после порога knee, а не обрезание
- **Формула:** `output = knee + max(value - knee, 0) * (1 - compression)`
- **По зонам (v6.5):** Rolloff применяется только к `highlights` и `face_skin` (не ко всему subject)
- **Параметры:** `rolloff_knee` (по умолч. 200), `rolloff_compression` (по умолч. 0.35) из config.yaml

## Known Limitations

### Preview ≠ Export: детекция лица и параметры

Предпросмотр (Web UI) и экспорт (CLI/API) обрабатывают изображения на разных разрешениях, что может приводить к расхождениям в результатах:

- **Размер изображения:** Preview уменьшает до 768px по длинной стороне, экспорт работает с полным разрешением. Это влияет на адаптивные параметры, которые зависят от размера (glow, face detection kernel).
- **Детекция лица:** Эвристика по профилю ширины маски использует скользящее среднее с kernel, пропорциональным высоте. При разной высоте сглаженный профиль отличается → позиция овала лица может смещаться на 1-5% между preview и export.
- **Glow:** В preview glow фиксируется на середине диапазона (deterministic), в экспорте — адаптивный расчёт. Поэтому preview-результат может отличаться от финального.
- **Рекомендация:** Для точного контроля позиции лица используйте FaceOval overlay в Web UI — заданный овал передаётся и в preview, и в export без изменений.

### Deprecated поле `brightness` → `stone_gamma`

Конфигурация использует `stone_gamma` (SOP 5.1) вместо устаревшего `brightness`. Если в `config.yaml` или через UI передан `brightness`, он автоматически мигрируется в `stone_gamma` с DeprecationWarning. Рекомендуется обновить конфигурацию вручную.

### Антиалиасный контур хромакея

Начиная с v5.0.0-dev контур хромакея использует OpenCV `cv2.LINE_AA` для субпиксельного антиалиасинга. Это требует `opencv-python` (~30MB). Если cv2 не установлен — fallback на GaussianBlur (видимая лесенка на диагоналях).

Контур вырезки хромакея — градиентная маска (soft-step вокруг threshold) вместо бинарного порога. Плавный контур без зазубрин на диагоналях. Параметр `contour_smooth_epsilon` deprecated (игнорируется).
