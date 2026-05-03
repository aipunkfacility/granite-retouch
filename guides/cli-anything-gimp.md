# Руководство: Окружение и Воркфлоу CLI-Anything + GIMP

## 1. Окружение

| Компонент | Путь |
|---|---|
| Python 3.14 | C:\Users\Аня\AppData\Local\Python\pythoncore-3.14-64\python.exe |
| uv (пакетный менеджер) | C:\Users\Аня\AppData\Local\Python\pythoncore-3.14-64\Scripts\uv.exe |
| cli-anything-gimp | C:\Users\Аня\AppData\Local\Python\pythoncore-3.14-64\Scripts\cli-anything-gimp.exe |
| GIMP 2.10 | F:\GIMP 2\bin\gimp-2.10.exe |
| gimp-console | F:\GIMP 2\bin\gimp-console-2.10.exe |
| Pillow | pip install Pillow через uv в среде Python 3.14 |

Переменные окружения (обязательно перед запуском CLI-Anything):
```powershell
$env:PATH += ";F:\GIMP 2\bin"
$env:GIMP_EXECUTABLE = "F:\GIMP 2\bin\gimp-2.10.exe"
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

$cli  = "C:\Users\Аня\AppData\Local\Python\pythoncore-3.14-64\Scripts\cli-anything-gimp.exe"
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

Для сложного постобработки (удаление синего хромакея, полукруглый вырез "Memorial Arch", Inner Glow) используется скрипт `prepare_vignette.py`.

**Скрипт:** `./prepare_vignette.py` (в корне проекта MEMORIAL)

Установка Pillow (если не установлен):
```powershell
C:\Users\Аня\AppData\Local\Python\pythoncore-3.14-64\Scripts\uv.exe pip install Pillow --python C:\Users\Аня\AppData\Local\Python\pythoncore-3.14-64\python.exe
```

Запуск скрипта:
```powershell
C:\Users\Аня\AppData\Local\Python\pythoncore-3.14-64\python.exe prepare_vignette.py
```

Скрипт создает два файла:
- `final_vignette.tiff` — производственный файл
- `final_vignette.png` — превью для визуальной проверки

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

```powershell
C:\Users\Аня\AppData\Local\Python\pythoncore-3.14-64\python.exe -c "from PIL import Image; Image.open('final.tiff').save('preview.png')"
```

## 6. Запасной план: Native GIMP Script-Fu

Если cli-anything-gimp падает с MemoryError (4ГБ ОЗУ не хватает
при рендере сложных масок), вся логика переносится в .scm-скрипт:

Скрипт размещается в: `memorial_process.scm`
Запуск через bat-обертку: `run_gimp.bat`

Причина: GIMP использует GEGL и файл подкачки Windows (swap) как буфер,
поэтому не падает при нехватке ОЗУ там, где Python+Pillow не справляется.

Шаблон bat-файла:
```bat
"F:\GIMP 2\bin\gimp-console-2.10.exe" -i -b "(begin (load \"путь/к/скрипту.scm\") (имя-функции \"вход.png\" \"выход.tiff\"))" -b "(gimp-quit 0)"
```

## 7. Важные ограничения и ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `Error: Neither GIMP nor Pillow available` | Не задан `GIMP_EXECUTABLE` | Установить переменную окружения |
| `MemoryError` при рендере | 4ГБ ОЗУ, Pillow загружает всё в RAM | Перейти на Script-Fu режим |
| `Error reading string` в gimp-console | Кавычки не правильно экранированы в PS | Завернуть команду в .bat-файл |
| `unbound variable: memorial-process-order` | Функция не загружена в ту же сессию | Свернуть load и вызов в один `(begin ...)` |
