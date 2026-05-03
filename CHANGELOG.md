# Changelog

Все заметные изменения в проекте granite-retouch фиксируются в этом файле.

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
