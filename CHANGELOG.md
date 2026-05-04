# Changelog

Все заметные изменения в проекте granite-retouch фиксируются в этом файле.

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
