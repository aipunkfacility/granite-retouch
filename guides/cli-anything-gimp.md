# Руководство: Окружение и Воркфлоу CLI-Anything + GIMP

## 1. Окружение

| Компонент | Как найти |
|---|---|
| Python 3.14 | Системный (`python --version`) |
| uv (пакетный менеджер) | `uv --version` (установлен через `curl -LsSf https://astral.sh/uv/install.sh \| sh`) |
| cli-anything-gimp | Установлен в `.venv` или глобально (`where cli-anything-gimp`) |
| GIMP 2.10 | Через `config.yaml` → `gimp.search_paths` или env var `GIMP_PATH` |
| Pillow + PyYAML | В `.venv` (`uv pip install Pillow PyYAML`) |

### Настройка venv (первый запуск)

```bash
cd /f/Dev/Projects/GRANITE/granite-retouch
uv venv --python python        # Использует системный Python
source .venv/Scripts/activate  # Git Bash
uv pip install Pillow PyYAML pytest
```

### Переменные окружения (обязательно перед запуском CLI-Anything)

```powershell
# PowerShell
$env:PATH += ";F:\GIMP 2\bin"
$env:GIMP_EXECUTABLE = "F:\GIMP 2\bin\gimp-2.10.exe"
```

```bash
# Git Bash
export PATH="$PATH;/f/GIMP 2/bin"
export GIMP_EXECUTABLE="F:\GIMP 2\bin\gimp-2.10.exe"
```

## 2. Команды cli-anything-gimp

Утилита использует stateful-проекты (JSON). Важные правила:
- **Параметры фильтров задаются ТОЛЬКО через `filter set`** (не через `filter add`).
- Индекс фильтра указывается числом и считается с 0 в порядке добавления.
- Формат `filter set`: `filter set --layer LAYER_INDEX FILTER_INDEX PARAM VALUE`.

Доступные фильтры и их параметры:
- `grayscale` — перевод в ЧБ (без параметров)
- `brightness` — factor: float (1.0 = нейтрально)
- `contrast` — factor: float (1.0 = нейтрально)
- `unsharp_mask` — radius: float, percent: int, threshold: int
- `sharpness` — factor: float
- `autocontrast` — без параметров
- `equalize` — без параметров
- `invert` — без параметров

### Форматы экспорта
- `tiff` — TIFF с LZW-сжатием (рекомендован для гравировки, lossless)
- `bmp` — BMP 8-bit (прямой формат некоторых станков)
- `png`, `jpeg-high`, `webp-lossless` — для предпросмотра

## 3. Полный воркфлоу постобработки

Пример: файл ai.png (896x1195), лазерный станок.

```powershell
$env:PATH += ";F:\GIMP 2\bin"
$env:GIMP_EXECUTABLE = "F:\GIMP 2\bin\gimp-2.10.exe"

$cli  = "cli-anything-gimp"
$proj = "orders\active\ORD-XXXX\project.json"
$src  = "orders\active\ORD-XXXX\ai.png"
$out  = "orders\active\ORD-XXXX\final.tiff"

# 1. Создать проект точно по размеру портрета
& $cli project new -w 896 -h 1195 -o $proj

# 2. Загрузить портрет как слой
& $cli --project $proj layer add-from-file $src

# 3. Grayscale (фильтр #0)
& $cli --project $proj filter add grayscale

# 4. Unsharp Mask (фильтр #1) — мягкая резкость
& $cli --project $proj filter add unsharp_mask
& $cli --project $proj filter set --layer 0 1 radius 1.0
& $cli --project $proj filter set --layer 0 1 percent 100

# 5. Contrast (фильтр #2) — без пересвета
& $cli --project $proj filter add contrast
& $cli --project $proj filter set --layer 0 2 factor 0.95

# 6. Рендер в TIFF
& $cli --project $proj export render $out -p tiff --overwrite
```

## 4. Виньетирование и визуальный вырез (Python + Pillow)

Для сложной постобработки (удаление синего хромакея, полукруглый вырез "Memorial Arch", Inner Glow) используется скрипт `prepare_vignette.py`.

**Скрипт:** `./prepare_vignette.py` (в корне проекта granite-retouch)

### Запуск скрипта

```bash
# Активировать venv
source .venv/Scripts/activate

# Лазерный станок (по умолчанию)
python prepare_vignette.py -i orders/active/ORD-2026-006/generated/ai.png -o orders/active/ORD-2026-006/generated/final_vignette.tiff -m laser

# Ударный станок
python prepare_vignette.py -i ai.png -o final_vignette.tiff -m impact

# Переопределить параметры Inner Glow
python prepare_vignette.py -i ai.png -o final.tiff -m laser --glow-size 50 --glow-opacity 35

# Пропустить валидацию (legacy-режим)
python prepare_vignette.py -i ai.png -o final.tiff -m laser --no-validate

# Указать путь к config.yaml
python prepare_vignette.py -i ai.png -o final.tiff -c /path/to/config.yaml
```

### Параметры CLI

| Параметр | Сокращение | Обязательный | Описание |
|----------|-----------|-------------|----------|
| `--input` | `-i` | Да | Путь к входному PNG (с синим хромакеем) |
| `--output` | `-o` | Да | Путь к выходному TIFF |
| `--machine` | `-m` | Нет | `laser` (default) или `impact` |
| `--glow-size` | — | Нет | Переопределить размер Inner Glow (px) |
| `--glow-opacity` | — | Нет | Переопределить opacity Inner Glow (%) |
| `--config` | `-c` | Нет | Путь к config.yaml (default: auto-detect) |
| `--no-validate` | — | Нет | Пропустить валидацию входа и результата |

### Валидация (автоматическая)

Скрипт проверяет входное изображение перед обработкой:
- Файл существует и открывается Pillow
- Разрешение >= 512x512 (настраивается в `config.yaml`)
- Присутствует синий хромакей (>= 15% синих пикселей)
- Результат содержит достаточно чёрного фона (>= 25%)

При ошибке валидации: `ValidationError` + exit code 1.

### Результат

Скрипт создаёт два файла:
- `{output}.tiff` — производственный файл
- `{output}.png` — превью для визуальной проверки

Путь к PNG генерируется автоматически из `--output` (заменяется расширение).

## 5. Проверка результата (обязательный шаг!)

После каждого рендера агент ОБЯЗАН:

1. Конвертировать TIFF → PNG
2. Проверить по чек-листу:

| # | Проверка | Описание |
|---|----------|----------|
| 1 | Фон чёрный | Абсолютно чёрный (#000000), без градиента |
| 2 | Лицо не пересвечено | Видны тени под глазами, на щеках |
| 3 | Детали волос | Сохранены пряди, объём |
| 4 | Воротник | Чёткий, контрастный |
| 5 | Края плавные | Arch mask — плавный переход |
| 6 | Голова видна целиком | Виньетка не обрезает верхнюю часть |

```bash
python -c "from PIL import Image; Image.open('final.tiff').save('preview.png')"
```

## 6. Запасной план: Native GIMP Script-Fu

Если cli-anything-gimp падает с MemoryError (4ГБ ОЗУ не хватает
при рендере сложных масок), вся логика переносится в .scm-скрипт:

**Скрипт:** `retouch_process.scm`
**Запуск через:** `python run_gimp.py -i <input> -o <output> -m <laser|impact>`

```bash
python run_gimp.py -i ai.png -o final.tiff -m laser
```

`run_gimp.py` автоматически:
1. Находит GIMP по `config.yaml` → `gimp.search_paths` или env var `GIMP_PATH`
2. Генерирует Scheme-команду с правильными путями и параметрами станка
3. Запускает GIMP в headless-режиме

Причина: GIMP использует GEGL и файл подкачки Windows (swap) как буфер,
поэтому не падает при нехватке ОЗУ там, где Python+Pillow не справляется.

## 7. Важные ограничения и ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `Error: Neither GIMP nor Pillow available` | Не задан `GIMP_EXECUTABLE` | Установить переменную окружения |
| `MemoryError` при рендере | 4ГБ ОЗУ, Pillow загружает всё в RAM | Перейти на Script-Fu режим |
| `Error reading string` в gimp-console | Кавычки не правильно экранированы в PS | Использовать `run_gimp.py` (автоэкранирование) |
| `unbound variable: retouch-process-order` | Функция не загружена в ту же сессию | Использовать `run_gimp.py` (оборачивает в `(begin ...)`) |
| `ValidationError: Синий хромакей не обнаружен` | На изображении нет синего фона | Проверить, что фон #0000FF; использовать `--no-validate` для обхода |
| `ValidationError: Разрешение ниже минимума` | Изображение меньше 512x512 | Использовать изображение большего размера |
