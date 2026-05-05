# Справочник CLI

Все команды granite-retouch запускаются через `python -m retouch` или `retouch` (если пакет установлен).

```
python -m retouch <command> [options]
```

---

## retouch process

Pillow-обработка портрета — основной путь для обоих типов станков.

```bash
python -m retouch process -i <input.png> -o <output.tiff> [-m laser|impact] [options]
```

### Аргументы

| Параметр | Сокращение | Обязательный | Описание |
|----------|-----------|-------------|----------|
| `--input` | `-i` | Да | Путь к входному PNG (с синим хромакеем) |
| `--output` | `-o` | Да | Путь к выходному TIFF |
| `--machine` | `-m` | Нет | Тип станка: `laser` (default) или `impact` |
| `--glow-size` | — | Нет | Переопределить размер Inner Glow (px) |
| `--glow-opacity` | — | Нет | Переопределить opacity Inner Glow (%) |
| `--config` | `-c` | Нет | Путь к config.yaml (default: автопоиск) |
| `--no-validate` | — | Нет | Пропустить валидацию входа и результата |

### Примеры

```bash
# Стандартная обработка — лазерный станок
python -m retouch process -i ai.png -o final.tiff -m laser

# Ударный станок
python -m retouch process -i ai.png -o final.tiff -m impact

# Переопределить Inner Glow
python -m retouch process -i ai.png -o final.tiff -m laser --glow-size 50 --glow-opacity 35

# Свой config.yaml
python -m retouch process -i ai.png -o final.tiff -c /path/to/config.yaml

# Пропустить валидацию (для нестандартных изображений)
python -m retouch process -i ai.png -o final.tiff --no-validate
```

### Результат

Создаёт два файла:
- `{output}.tiff` — производственный файл для станка
- `{output}.png` — превью для визуальной проверки

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
python -m retouch gimp -i <input.png> -o <output.tiff> [-m laser|impact] [options]
```

При запуске выводит предупреждение: «Experimental: results may be incorrect. Use `retouch process` for production.»

### Аргументы

| Параметр | Сокращение | Обязательный | Описание |
|----------|-----------|-------------|----------|
| `--input` | `-i` | Да | Путь к входному PNG |
| `--output` | `-o` | Да | Путь к выходному TIFF |
| `--machine` | `-m` | Нет | `laser` (default) или `impact` |
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
ORD-2026-001       laser     done                          Иванов И.И.
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
python -m retouch order create <order_id> [--crm CMP-NNNN] [-m laser|impact]
```

| Параметр | Описание |
|----------|----------|
| `order_id` | ID заказа (напр. `ORD-2026-042`). Формат: `ORD-YYYY-NNN` |
| `--crm` | ID компании в CRM (напр. `CMP-0042`) |
| `-m` | Тип станка: `laser` (default) или `impact` |

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

## Установка

```bash
cd granite-retouch
uv venv --python python
source .venv/Scripts/activate   # Git Bash на Windows
uv pip install -e ".[dev]"
```

После установки доступна команда `retouch` (без `python -m`).
