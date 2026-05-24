# Справочник CLI

Все команды granite-retouch запускаются через `uv run python -m retouch` или `retouch` (если пакет установлен).

```
uv run python -m retouch <command> [options]
```

> Если пакет установлен в системный Python — можно опустить `uv run` и запускать `python -m retouch` напрямую.

---

## retouch process

Pillow-обработка портрета — основной путь для всех типов станков.

```bash
python -m retouch process -i <input.png> -o <output.bmp> [-m laser_standard|laser_80w|impact] [options]
```

### Аргументы

| Параметр | Сокращение | Обязательный | Описание |
|----------|-----------|-------------|----------|
| `--input` | `-i` | Да | Путь к входному PNG (с синим хромакеем) |
| `--output` | `-o` | Да | Путь к выходному файлу (BMP по умолчанию) |
| `--machine` | `-m` | Нет | Тип станка: `laser_standard` (default), `laser_80w` или `impact` |
| `--preset` | — | Нет | Имя пресета из `presets/` (напр. `stanzone-laser-1bit`, `mirtels-impact`). Накладывается поверх config.yaml |
| `--material` | — | Нет | Тип материала: `granite`, `marble`, `gabbro`, `basalt`, `acrylic`. Применяет автокоррекции из MATERIAL_PROFILES |
| `--stone` | — | Нет | **DEPRECATED** — используйте `--material` |
| `--profile` | — | Нет | Профиль обработки: `standard` (default), `preserve` или `diagnostic` |
| `--format` | `-f` | Нет | Формат экспорта: `bmp` (default), `bmp_1bit`, `bmp_8bit`, `png`, `tiff` |
| `--glow-size` | — | Нет | Переопределить размер Glow (px) |
| `--glow-opacity` | — | Нет | Переопределить opacity Glow (%) |
| `--config` | `-c` | Нет | Путь к config.yaml (default: автопоиск) |
| `--no-validate` | — | Нет | Пропустить валидацию входа и результата |
| `--overwrite` | — | Нет | Перезаписать выходной файл без подтверждения. Без флага — exit(1) если файл существует |
| `--face-oval` | — | Нет | Ручное задание овала лица: `CX,CY,RX,RY` (нормализованные 0–1). Переопределяет авто-детекцию. Передаётся из Web UI в export для preview-export consistency |

### Примеры

```bash
# Стандартная обработка — лазерный станок 20-40W (BMP 8-bit grayscale)
python -m retouch process -i ai.png -o final.bmp -m laser_standard

# Мощный лазер 60-80W+ — BMP 1-bit с Jarvis дизерингом
python -m retouch process -i ai.png -o final.bmp -m laser_80w

# Ударный станок — BMP 8-bit grayscale
python -m retouch process -i ai.png -o final.bmp -m impact

# Явно указать 1-bit BMP для laser_80w
python -m retouch process -i ai.png -o final.bmp -m laser_80w --format bmp_1bit

# Экспорт в PNG (для предпросмотра / совместимости)
python -m retouch process -i ai.png -o final.png -m laser_standard --format png

# Экспорт в TIFF (legacy / совместимость)
python -m retouch process -i ai.png -o final.tiff -m laser_standard --format tiff

# Переопределить Glow (стиль зависит от типа станка: Outer для лазера, Inner для impact)
python -m retouch process -i ai.png -o final.bmp -m laser_standard --glow-size 50 --glow-opacity 35

# Свой config.yaml
python -m retouch process -i ai.png -o final.bmp -c /path/to/config.yaml

# Пропустить валидацию (для нестандартных изображений)
python -m retouch process -i ai.png -o final.bmp --no-validate

# Перезаписать существующий выходной файл
python -m retouch process -i ai.png -o final.bmp --overwrite
```

### Результат

По умолчанию (формат `bmp`) создаёт два файла:
- `{output}.bmp` — производственный файл для станка
  - **laser_standard**: 8-bit grayscale BMP (256 оттенков, палитра R=G=B)
  - **laser_80w**: 1-bit монохромный BMP с Jarvis дизерингом
  - **impact**: 1-bit монохромный BMP с Stucki дизерингом
- `{output}.png` — превью для визуальной проверки

Формат `--format` позволяет явно выбрать:
- `bmp` — автоматически: 8-bit для laser_standard/impact, 1-bit для laser_80w
- `bmp_8bit` — принудительно 8-bit grayscale BMP
- `bmp_1bit` — принудительно 1-bit BMP с Jarvis/Stucki дизерингом
- `png` — PNG (grayscale/RGB)
- `tiff` — TIFF с LZW-сжатием (legacy)

---

## retouch validate

Валидация входного изображения без обработки.

```bash
python -m retouch validate -i <input.png> [options]
```

### Аргументы

| Параметр | Сокращение | Обязательный | Описание |
|----------|-----------|-------------|----------|
| `--input` | `-i` | Да | Путь к изображению |
| `--config` | `-c` | Нет | Путь к config.yaml |

### Проверки

1. Файл существует и открывается Pillow
2. Разрешение >= 512x512 (настраивается: `processing.min_resolution`)
3. Присутствует синий хромакей >= 15% пикселей (настраивается: `processing.min_blue_ratio`)

### Примеры

```bash
python -m retouch validate -i ai.png
# OK: ai.png — 34.2% blue pixels

python -m retouch validate -i photo.jpg
# FAIL: Синий хромакей не обнаружен (синих пикселей: 2.1%)
```

---

## retouch gimp

GIMP-обработка через Script-Fu. **Experimental / не рекомендуется для production** — используйте `retouch process`.

```bash
python -m retouch gimp -i <input.png> -o <output.bmp> [-m laser_standard|laser_80w|impact] [options]
```

При запуске выводит предупреждение: «Experimental: results may be incorrect. Use `retouch process` for production.»

### Аргументы

| Параметр | Сокращение | Обязательный | Описание |
|----------|-----------|-------------|----------|
| `--input` | `-i` | Да | Путь к входному PNG |
| `--output` | `-o` | Да | Путь к выходному файлу |
| `--machine` | `-m` | Нет | `laser_standard` (default), `laser_80w` или `impact` |
| `--config` | `-c` | Нет | Путь к config.yaml |

### Когда использовать GIMP

Единственный случай: Pillow падает с MemoryError на очень больших изображениях при ограниченной ОЗУ. GIMP использует GEGL и файл подкачки, поэтому справляется с большими файлами.

---

## retouch order

Управление заказами.

### retouch order list

Показать список всех активных заказов.

```bash
python -m retouch order list
```

Формат вывода:

```
Order ID           Machine   Status           CRM          Client
---------------------------------------------------------------------------
ORD-2026-001       laser_standard     done                    Иванов И.И.
ORD-2026-007       impact    done             CMP-0042     Петров П.П.
```

### retouch order validate

Валидация order.json по schema.json.

```bash
python -m retouch order validate <order_id|path>
```

| Аргумент | Описание |
|----------|----------|
| `order_id` | ID заказа (напр. `ORD-2026-001`) или путь к order.json |

Примеры:

```bash
python -m retouch order validate ORD-2026-001
# OK: orders/active/ORD-2026-001/order.json (no CRM link)

python -m retouch order validate ORD-2026-007
# OK: orders/active/ORD-2026-007/order.json (CRM: CMP-0042)

python -m retouch order validate /path/to/order.json
```

### retouch order create

Создать новый заказ из шаблона.

```bash
python -m retouch order create <order_id> [--crm CMP-NNNN] [-m laser_standard|laser_80w|impact]
```

| Параметр | Описание |
|----------|----------|
| `order_id` | ID заказа (напр. `ORD-2026-042`). Формат: `ORD-YYYY-NNN` |
| `--crm` | ID компании в CRM (напр. `CMP-0042`) |
| `-m` | Тип станка: `laser_standard` (default), `laser_80w` или `impact` |

Примеры:

```bash
# Простой заказ
python -m retouch order create ORD-2026-042

# С привязкой к CRM и ударным станком
python -m retouch order create ORD-2026-042 --crm CMP-0042 -m impact
```

Создаёт:
- `orders/active/ORD-2026-042/order.json`
- `orders/active/ORD-2026-042/generated/`

Следующий шаг: `copy source.jpg → orders/active/ORD-2026-042/source.jpg`

---

## retouch debug report

Попиксельный анализ результата пайплайна (диагностика).

```bash
python -m retouch debug report -i <source.png> -o <result.bmp> [options]
```

### Аргументы

| Параметр | Сокращение | Обязательный | Описание |
|----------|-----------|-------------|----------|
| `--input` | `-i` | Да | Исходное изображение (source) |
| `--output` | `-o` | Да | Результат пайплайна (output) |
| `--machine` | `-m` | Нет | `laser_standard` (default), `laser_80w` или `impact` |
| `--face-mask` | `-f` | Нет | Путь к маске лица (PNG) |
| `--subject-mask` | `-s` | Нет | Путь к маске субъекта (PNG) |
| `--output-dir` | `-d` | Нет | Папка для отчётов (JSON+TXT+heatmap) |
| `--json` | — | Нет | Путь для JSON отчёта |
| `--txt` | — | Нет | Путь для текстового отчёта |
| `--heatmap` | — | Нет | Путь для heatmap PNG |

---

## Глобальные флаги

### --list-presets

Показать список всех доступных пресетов из `PRESET_CATALOG`.

```bash
python -m retouch --list-presets
```

Вывод: категория, название, machine_type, alert (если есть).

---

## Установка

```bash
cd granite-retouch
uv venv --python python
source .venv/Scripts/activate   # Git Bash на Windows
uv sync --extra dev
```

После установки доступна команда `retouch` (без `python -m`).
