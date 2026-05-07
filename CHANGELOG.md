# Changelog

Все заметные изменения в проекте granite-retouch фиксируются в этом файле.

## [3.1.0] - 2026-05-08

### 💥 Breaking Changes

- **Формат экспорта по умолчанию**: TIFF → BMP. CLI теперь сохраняет BMP вместо TIFF. Для совместимости доступен `--format tiff`.
- **Схема face_brightness_target**: формат списка `[min, max]` заменён на отдельные ключи `face_brightness_target_min` / `face_brightness_target_max`. Старый формат автоматически мигрируется при загрузке.
- **Порт Web UI**: 8001 → 8000. Vite proxy и Makefile обновлены. Если запускаете uvicorn вручную — используйте `uv run uvicorn ... --port 8000`.

### ✨ Новые возможности

- **BMP экспорт** (`retouch/processing/export.py`): 8-bit grayscale BMP для laser_standard/impact, 1-bit BMP с Floyd-Steinberg дизерингом для laser_80w
- **CLI `--format`**: новый аргумент — `bmp` (default), `bmp_1bit`, `bmp_8bit`, `png`, `tiff`
- **White ceiling**: параметр `white_ceiling` ограничивает максимальную яркость пикселей (кроме зрачков). laser_standard: 250, laser_80w: 235, impact: 240
- **Shadow noise**: `add_shadow_noise()` для impact — шум в глубоких тенях даёт игле «зацепку» (параметры `shadow_noise_min`/`shadow_noise_max`)
- **Pillow-fallback warning**: если numpy недоступен, `check_face_brightness()` логирует предупреждение о том, что масочная защита отключена

### 🐛 Исправления

- **Double brightening**: исправлен баг двойного усиления яркости (Levels ×1.35 + Face Correction ×1.20) — теперь адаптивный фактор + face correction работают корректно
- **Laser 80W face targets**: восстановлены экспертные значения 190–210 (commit b183522 ошибочно снизил до 150–170)
- **Web UI port mismatch**: Vite proxy указывал на 8001, uvicorn слушал 8000 → таймаут загрузки 30 сек

### 📚 Документация

- Обновлены все ссылки TIFF → BMP в: README, getting-started, cli.md, config.md, pipeline.md, overview.md, vignette.md
- Добавлены новые параметры: white_ceiling, shadow_noise_min/max, face_brightness_target_min/max
- webui-setup.md: порт 8000, troubleshooting «Загрузка превышена»
- BACKLOG-006: shadow_noise отмечен как реализованный

## [4.0.0] - 2026-05-07

### 💥 Breaking Changes

- **`machine_type` расширение**: значение `"laser"` заменено на `"laser_standard"`. Старое значение `"laser"` вызывает ошибку валидации в schema.json. Если в order.json указан `"machine_type": "laser"` — замените на `"laser_standard"`.
- **`config.yaml` ключи**: секция `processing.laser:` переименована в `processing.laser_standard:`. Добавлена секция `processing.laser_80w:`.

### ✨ Новые возможности

- **Пресет laser-80w.md**: новый стиль для мощных лазеров (60-80W+) — medium-key, тёмные волосы, сохранённые морщины, потолок яркости 235
- **26 промпт-правок** (B1–B16, C-L0/L2/L3, C-I1/I2/I3): уточнение Goal, clothing blowout, серебряный тон, скульптурный объём волос, «лучше темнее»
- **Модуль преданализа** (`retouch/processing/analysis.py`): 13 метрик входного изображения для адаптивных доработок пайплайна
- **Адаптивный Levels** (P2): фактор яркости вычисляется из analytics вместо фиксированного 1.18, защита от клиппинга
- **Адаптивный Glow** (P3): параметры glow рассчитываются из analytics (subject_separation, tonal_range)
- **Адаптивный Unsharp** (P5): percent вычисляется из analytics (input_class, tonal_range)
- **Целевые значения по пресету** (P4): config.yaml содержит 3 секции — laser_standard, laser_80w, impact
- **Масочная защита** (P6): `apply_levels()` и `apply_unsharp_mask()` принимают `subject_mask`, коррекция только внутри маски
- **P6.4 Pillow-fallback mask**: `check_face_brightness()` Pillow-ветка теперь ограничивает коррекцию внутри маски субъекта через numpy пост-обработку
- **PipelineResult.analytics**: dict с метриками преданализа доступен после обработки
- **34 новых TDD-теста** для этапов 5–11 дев-плана

### 🐛 Исправления

- **BUG-C**: impact face_brightness_target поднят с [185, 210] до [200, 225] — устраняет плоские лица на impact-гравировке
- **CLI docstring**: обновлён с `-m laser_standard` вместо устаревшего `-m laser`
- **Промпты**: убрано дублирование фраз про «flat hair» в laser.md §2 и impact.md §2

## [3.0.0] - 2026-05-05

### 💥 Breaking Changes

- **`check_face_brightness()` return**: функция теперь возвращает кортеж `(img, before, after, factor)` вместо одного значения `Image`. Первым элементом — скорректированное изображение, затем яркость до, яркость после и множитель коррекции. Код, ожидавший только `Image`, нужно обновить: `result, before, after, factor = check_face_brightness(...)`.
- **`load_config()` deep_merge**: конфиг теперь загружается с `deep_merge` — пользовательский конфиг мержится с defaults рекурсивно, а не заменяет целые секции. Если вы полагались на полную замену секции — используйте пустые значения явно.
- **`process()` wrapper**: функция `process()` теперь обёрнута в `process_steps()` / `process_preview()` / `process_export()`. Старый вызов `process()` с полным набором аргументов может вести себя иначе — используйте новые функции.

### ✨ Новые возможности

- **Web UI**: интерактивный интерфейс для настройки параметров ретуши с живым предпросмотром
  - FastAPI backend (`retouch_ui/backend/`) с роутерами: upload, process/preview, process/export, config, presets
  - React + Vite frontend (`retouch_ui/frontend/`) со слайдерами, компаратором до/после, диагностикой
  - Запуск: `make ui` (dev) или `make ui-prod` (production, один процесс)
  - Production: FastAPI раздаёт статику через `StaticFiles` — достаточно одного uvicorn
- **`PipelineResult`**: новый класс результата обработки с промежуточными изображениями, диагностикой и `release_intermediates()`
- **`process_steps()` / `process_preview()` / `process_export()`**: специализированные функции вместо одной `process()`
- **Пресеты**: директория `presets/` с YAML-файлами (laser-default, laser-dark-portrait, impact-default, impact-soft)
- **Pydantic-модели**: валидация запросов/ответов backend через Pydantic (UploadResponse, PreviewRequest, ExportRequest, HealthResponse)
- **Параметры `face_region_top` и `highlight_start`**: контроль области замера яркости и защита от пересвета

### 🐛 Исправления

- **Fringe test**: исправлен тест fringe removal — корректная проверка синего канала в переходной зоне
- **File descriptor leak**: временные файлы экспорта удаляются через `BackgroundTask` после отдачи клиенту
- **Config overwrite**: `load_config()` с `deep_merge` — пользовательский конфиг больше не затирает defaults неявно

## [2.6.0] - 2026-05-04

### 🧪 Тестирование (Фаза 7)

- **`tests/conftest.py`:** фикстуры для синтетических изображений с хромакеем
  - `make_chromakey_image()` — RGBA с синим фоном и эллипсом-субъектом
  - `make_no_chromakey_image()` — без хромакея (негативные тесты)
  - `make_dark_blue_clothing_image()` — тёмно-синяя одежда (граничный кейс)
  - Фикстуры: `chromakey_png`, `small_chromakey_png`, `no_chromakey_png`, `valid_order_json`, etc.
- **`tests/test_chromakey.py`** (7 тестов): удаление синего фона, сохранение субъекта, fringe removal, тёмно-синяя одежда, режимы RGBA/L
- **`tests/test_glow.py`** (6 тестов): laser/impact glow размеры, яркость контура, случайный glow в диапазоне, минимальная opacity
- **`tests/test_levels.py`** (10 тестов): brightness, unsharp mask, curves-коррекция (тени/света), сжатие маски, контроль яркости лица
- **`tests/test_vignette.py`** (7 тестов): RGB-результат, чёрные углы, headroom, масштабирование, плавная маска
- **`tests/test_validation.py`** (16 тестов): валидация изображения, хромакей, чёрный фон, order.json (валидные/невалидные, CRM, формат ID)
- **`tests/test_config.py`** (10 тестов): DEFAULTS-структура, диапазоны glow/brightness, загрузка из файла, fallback
- **`tests/test_pipeline.py`** (8 тестов): интеграция — laser/impact полный пайплайн, чёрный фон, отсутствие пересвета, no-validate режим

**Итого: 72 теста, все проходят.**

## [2.5.0] - 2026-05-04

### 📚 Модуляризация документации

- **`docs/`** — единая директория документации (вместо разброса по 6 местам)
  - `docs/index.md` — карта документации
  - `docs/getting-started.md` — быстрый старт за 5 шагов (заменяет workflow.md)
  - `docs/reference/cli.md` — полный справочник CLI
  - `docs/reference/config.md` — все параметры config.yaml с диапазонами
  - `docs/reference/order-schema.md` — поля order.json
  - `docs/guides/vignette.md` — обновлено (ссылки на `python -m retouch process`)
  - `docs/guides/style-guide-laser.md` — стиль лазерной генерации
  - `docs/guides/style-guide-impact.md` — **НОВЫЙ**: стиль ударной генерации
  - `docs/guides/nano-banana.md` — работа с Nano Banana
  - `docs/architecture/overview.md` — структура проекта, потоки данных
  - `docs/architecture/pipeline.md` — пайплайн обработки + диагностика проблем
  - `docs/integration/crm.md` — связь с granite-crm
- **AGENTS.md** → сокращён до навигатора (~80 строк вместо 354)
- **README.md** → обновлён: CLI-команды, ссылки на docs/
- **workflow.md** → редирект на docs/getting-started.md
- **BACKLOG.md** → версия исправлена на 2.4.0
- **retouch-prompter/SKILL.md** → исправлена ссылка: `prompt_blocks/machine/` → `prompt_blocks/`
- Стиль переименован: «Memorial High-End Airbrush» → «Granite High-End Airbrush»

## [2.4.0] - 2026-05-04

### 🔗 Интеграция с granite-crm (Фаза 6)

- **CLI `retouch order`:** управление заказами из командной строки
  - `retouch order list` — список активных заказов (ID, станок, статус, CRM-привязка, клиент)
  - `retouch order validate ORD-2026-001` — валидация order.json по schema.json
  - `retouch order create ORD-2026-042 --crm CMP-0042 -m impact` — создание заказа из шаблона с привязкой к CRM
- **CRM-связь:** поле `crm_company_id` в order.json (формат `CMP-NNNN`) — конвенционная связь заказов с компаниями в granite-crm
  - `schema.json`: добавлен `pattern: "^CMP-\\d{4}$"` для валидации ID
  - `orders/template/order.json`: поле `crm_company_id` включено в шаблон
- **config.yaml:** секция `crm:` с путём к granite-crm (`crm_path`) и переменной окружения (`GRANITE_CRM_PATH`)
- **GIMP-команда:** помечена как experimental / not recommended (предупреждение при запуске `retouch gimp`)
- **AGENTS.md:** обновлено дерево структуры (добавлен `retouch/` пакет, `BACKLOG.md`, `Makefile`), добавлена секция «Интеграция с granite-crm»
- **BACKLOG.md:** создан product backlog проекта (11 задач P0–P3)

## [2.3.1] - 2026-05-04

### 🔧 Дозакрытие Фазы 5

- **`retouch/__main__.py`:** добавлен — `python -m retouch` теперь работает (раньше: `No module named retouch.__main__`)
- **Корневые скрипты → тонкие обёртки:** `prepare_vignette.py` и `run_gimp.py` делегируют в `retouch.cli`, дублирование кода устранено
  - Если пакет не установлен — понятная ошибка с инструкцией `uv pip install -e .`
- **Makefile:** шорткаты для повседневных команд (`make process`, `make validate`, `make gimp`, `make test`, `make install-dev`)

## [2.3.0] - 2026-05-04

### 🏗️ Реструктуризация архитектуры (Фаза 5)

- **Пакет `retouch/`:** код вынесен из монолитных скриптов в модульную структуру
  - `retouch/config.py` — загрузка config.yaml
  - `retouch/cli.py` — единая точка входа (`python -m retouch process|validate|gimp`)
  - `retouch/processing/chromakey.py` — удаление синего фона + fringe removal
  - `retouch/processing/glow.py` — Inner Glow (contour light)
  - `retouch/processing/levels.py` — Levels + Unsharp Mask + контроль яркости
  - `retouch/processing/vignette.py` — арховая виньетка
  - `retouch/processing/pipeline.py` — полный пайплайн
  - `retouch/gimp/runner.py` — поиск и запуск GIMP
  - `retouch/validation/image.py` — валидация изображения и хромакея
  - `retouch/validation/order.py` — валидация order.json по schema.json
- **CLI:** `python -m retouch process -i ... -o ... -m laser`
- **pyproject.toml:** `retouch` CLI entry point, `packages = ["retouch"]`
- **Обратная совместимость:** `prepare_vignette.py` и `run_gimp.py` в корне по-прежнему работают

## [2.2.0] - 2026-05-04

### ⚡ Оптимизация обработки (Фаза 4)

- **numpy-ускорение:** `list(img.getdata())` заменён на `np.array()` — ~50x быстрее для 2048x2048
  - `remove_blue_background()` — numpy + scipy.ndimage.binary_dilation
  - `validate_blue_chromakey()` — numpy-подсчёт вместо Python-loop
  - `validate_result_black_ratio()` — numpy вместо list comprehension
  - Pillow-fallback сохранён (работает без numpy, но медленнее)
- **Fringe removal:** мягкое гашение синего канала в переходной зоне (артефакты хромакея на волосах/краях)
  - `fringe_radius` в config.yaml (default: 3, 0 = отключено)
  - numpy: binary_dilation + weighted blue damping
  - Pillow: pixel-level fallback
- **Контроль яркости лица:** `check_face_brightness()` — проверка средней яркости субъекта
  - laser: целевой диапазон 230-245, impact: 220-235
  - Автокоррекция brightness factor если вне диапазона (0.85-1.25)
  - Работает с numpy и Pillow (ImageStat fallback)
- **Зависимости:** добавлены `numpy>=1.24.0`, `scipy>=1.10.0` в pyproject.toml и requirements.txt

## [2.1.0] - 2026-05-04

### 🛡️ Валидация и обработка ошибок (Фаза 3)

- **prepare_vignette.py:**
  - `validate_image_input()` — проверка существования файла, формата, разрешения (>=512x512)
  - `validate_blue_chromakey()` — проверка наличия синего хромакея (минимум 15% синих пикселей)
  - `validate_result_black_ratio()` — проверка результата (минимум 25% чёрного фона)
  - Класс `ValidationError` с понятными сообщениями об ошибках
  - Флаг `--no-validate` для обхода валидации
  - Автосоздание директории для выходного файла
  - Исправлена генерация PNG-имени когда выходной файл не .tiff
- **config.yaml:** добавлены параметры `min_blue_ratio`, `min_resolution`, `result_min_black_ratio`
- **pyproject.toml:** добавлен `[build-system]`, явное указание `py-modules` и `packages = []` (исправлена ошибка setuptools flat-layout)
- **.gitignore:** убраны `*.lock` и `uv.lock` — lock-файлы должны коммититься

## [2.0.0] - 2026-05-04

### 🔄 Миграция

- Проект переименован: MEMORIAL → granite-retouch
- funeral-scraper удалён из документации (функции перенесены в granite-crm)
- `.agents/skills/` переименованы: memorial-* → retouch-*
- `memorial_process.scm` → `retouch_process.scm`
- `prepare_vignette.py`: функция `apply_memorial_processing` → `apply_retouch_processing`
- `run_gimp.bat` → `run_gimp.py` (Python CLI с автопоиском GIMP)
- Удалены `vibe.bat`, `projects/`, `sdk_page_reader_agent_guide.md`, `cities_russia_500k.md`

### 🐛 Исправления

- **prepare_vignette.py:** параметр `machine_type` теперь реально используется — impact и laser имеют разные параметры Inner Glow и яркости
- **retouch_process.scm:** виньетка масштабируется по размеру изображения (вместо захардкоженных 400/800 px)
- **retouch_process.scm:** добавлен параметр `machine-type` для дифференциации Inner Glow (shrink, feather, opacity)

### ✨ Новые возможности

- **prepare_vignette.py:** CLI через argparse (`--input`, `--output`, `--machine`, `--glow-size`, `--glow-opacity`)
- **run_gimp.py:** Python-скрипт с автопоиском GIMP по стандартным путям и env var `GIMP_PATH`
- **orders/schema.json:** добавлен `pattern` для `order_id`, `enum` для `clothing_style`/`headgear`/`face_quality`, поле `crm_company_id`
- **.gitignore:** защита от попадания бинарников из orders/active/

## [1.2.0] - 2026-03-14

### ✨ Новые возможности

- **funeral-agency-db:** Новая подсистема для сбора базы ритуальных агентств и производителей памятников по городам России.
  - Поиск организаций в 2GIS, Яндекс.Картах, справочниках (Yell.ru, JSprav.ru)
  - Обязательный поиск Telegram/WhatsApp по номерам телефонов
  - Приоритет контактов: Telegram > WhatsApp > Email > Телефон
  - Формат ссылок: t.me/username, wa.me/79xxxxxxxxx
  - Сбор данных по 26+ организациям в каждом городе

### 🔧 Улучшения

- **AGENTS.md:** Обновлена структура проекта, добавлена документация по funeral-scraper
- **README.md:** Добавлена секция funeral-agency-db
- **Агент funeral-scraper:** Обновлены инструкции с приоритетом Telegram

## [1.1.0] - 2026-03-11

### ✨ Новые возможности

- **AGENTS.md**: Создано руководство для ИИ-агентов с полной документацией по проекту.
  - Команды для валидации JSON
  - Стиль кода (Markdown, JSON, файлы)
  - Инструкции по работе с агентами
  - Соглашения об именовании

### 🔧 Улучшения

- **Структура документации**: Добавлена ссылка на AGENTS.md в README.md

## [1.0.0] - 2026-03-11

### ✨ Новые возможности

- **Агентская архитектура (Antigravity Skills):**
  - Навык `memorial-analyzer` — анализ фото и заполнение профиля заказа
  - Навык `memorial-prompter` — сборка промптов из атомарных блоков
  - Чек-лист `memorial-postprocessing` — подготовка к гравировке в Photoshop
- **Управление заказами:**
  - Структура папок: `orders/active/`, `orders/archive/`
  - JSON-схема `orders/schema.json` для стандартизации
  - Шаблон заказа и тестовый пример `TEST_ORDER`
- **База знаний:**
  - Спецификация [лазерных](knowledge/machines/laser.md) и [ударных](knowledge/machines/impact.md) станков
  - Принципы ретуши в `knowledge/principles.md`
- **Библиотека промптов:**
  - Блоки для базовых инструкций, станков, одежды, головных уборов
- **Навигация:** Переработан `workflow.md`

### 🔧 Улучшения

- **README.md**: Обновлен с учетом агентской структуры
- **Workflow**: Переход на итеративное взаимодействие с агентами

### 🗑 Удалено

- Устаревшая документация: `pipeline_laser.md`, `pipeline_impact.md`, `правки портрета.txt`

## [0.1.0] - 2026-03-10

- Начальная версия с базовой документацией по пайплайнам
