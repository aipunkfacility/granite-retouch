# API Reference

## Health

### GET /api/health

Проверка доступности бэкенда.

**Response:**

```json
{
  "status": "ok",
  "version": "6.2.0"
}
```

---

## Config

### GET /api/config

Получить текущую конфигурацию проекта.

**Response:**

```json
{
  "config": { ... },
  "warnings": []
}
```

### PUT /api/config

Обновить конфигурацию. Использует `deep_merge` с DEFAULTS — отсутствующие ключи заполняются.

**Request:**

```json
{
  "config": { ... }
}
```

**Response:**

```json
{
  "saved": true,
  "path": "/path/to/config.yaml",
  "warnings": []
}
```

### GET /api/config/defaults

Получить дефолтную конфигурацию (DEFAULTS из config.py).

---

## Presets

### GET /api/presets/catalog

Вернуть PRESET_CATALOG — UI-метаданные (бренд, категория, alert, combo_group).

**Response:**

```json
{
  "catalog": {
    "mirtels-impact": {
      "label": "Mirtels (ударный, все модели)",
      "category": "machine",
      "machine_type": "impact",
      "brand": "mirtels",
      "combo_group": "mirtels"
    },
    "stanzone-laser-1bit": {
      "label": "Stanzone (лазер, 1-bit)",
      "category": "machine",
      "machine_type": "laser_80w",
      "brand": "stanzone",
      "combo_group": "stanzone",
      "alert": "Лазерный модуль Stanzone работает ТОЛЬКО в 1-bit!"
    }
  }
}
```

### GET /api/presets

Получить список всех пресетов с полным конфигом.

**Response:**

```json
{
  "presets": [
    { "name": "mirtels-impact", "config": { ... } },
    { "name": "laser-default", "config": { ... } }
  ]
}
```

### POST /api/presets

Создать новый пресет.

### DELETE /api/presets/{name}

Удалить пресет по имени.

---

## Material

### GET /api/material/profiles

Вернуть MATERIAL_PROFILES для фронтенда: диапазоны, подсказки, hints. Вызывается один раз при загрузке приложения и кэшируется.

**Response:**

```json
{
  "profiles": {
    "granite": {
      "step_mm_range": [0.250, 0.300],
      "stone_gamma_range": [0.85, 0.90],
      "shadow_floor": 8,
      "white_ceiling_offset": 0,
      "notes": "Крупнозернистый — «съедает» контраст. Переконтрастированная ретушь.",
      "hints": {
        "laser_80w": "white_ceiling ≤ 235 — при 80W значения > 235 пережигаются"
      }
    },
    "acrylic": {
      "step_mm_range": [0.127, 0.150],
      "stone_gamma_range": [0.88, 1.0],
      "shadow_floor": 5,
      "white_ceiling_offset": 0,
      "export_mode_override": "1bit",
      "dither_method_override": "jarvis",
      "notes": "Лазерная гравировка акрила: BMP 1-bit + Jarvis/Diffusion.",
      "hints": {
        "laser_80w": "BMP 1-bit + Jarvis, 200 dpi, 300 мм/с (мануал Mirtels)",
        "laser_standard": "BMP 1-bit + Jarvis, 200 dpi, 300 мм/с (мануал Mirtels)"
      },
      "incompatible_machine_types": ["impact"]
    }
  }
}
```

### POST /api/material/apply

Применить material overrides + validation + hint. Вызывается ПЕРЕД preview — оператор видит автокоррекции до запуска обработки и может отказаться от смены материала.

**Request:**

```json
{
  "material": "acrylic",
  "machine_type": "laser_80w",
  "config": { ... }
}
```

- `material` (обязательный) — тип материала: `granite|marble|gabbro|basalt|acrylic`
- `machine_type` (обязательный) — тип станка: `laser_standard|laser_80w|impact`
- `config` (опциональный) — текущий конфиг для вычисления diffs. Если не указан — используются DEFAULTS.

**Response:**

```json
{
  "config_patch": {
    "stone": { "material": "acrylic", "type": "acrylic" },
    "processing": { "laser_80w": { "export_mode": "1bit", "dither_method_1bit": "jarvis", "step_mm": 0.15 } }
  },
  "changes": [
    { "param": "step", "old": 0.250, "new": 0.150, "reason": "выше диапазона acrylic (0.127–0.150)" },
    { "param": "export_mode", "old": "8bit", "new": "1bit" },
    { "param": "dither", "old": "jarvis", "new": "jarvis" }
  ],
  "validation_warnings": [],
  "active_hint": "BMP 1-bit + Jarvis, 200 dpi, 300 мм/с (мануал Mirtels)"
}
```

**Коды validation_warnings:**

| Комбинация | Уровень | Сообщение |
|:----------:|:-------:|-----------|
| acrylic + impact | ERROR | Акрил не поддерживает ударную гравировку |
| marble + impact | WARNING | Мрамор хрупкий — лазер предпочтительнее |
| laser_80w + granite | WARNING | white_ceiling ≤ 235 — пережигание |

---

## Process

### POST /api/upload

Загрузить изображение на сервер. Возвращает `file_id` для последующих операций.

**Клиентская валидация** (до отправки запроса):

| Проверка | Условие | Сообщение |
|:---|:---|:---|
| Формат файла | Расширение в `[".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"]` | "Неподдерживаемый формат: {ext}. Допустимы: ..." |
| Размер файла | ≤ 50 MB | "Файл слишком большой ({size} MB). Максимум: 50 MB" |

### POST /api/process/preview

Предпросмотр обработки. Возвращает JSON с base64-картинками по шагам + диагностика.

**Request:**

```json
{
  "file_id": "uuid",
  "machine": "laser_standard",
  "params": {
    "material": "granite",
    "preset": "mirtels-impact",
    "face_oval": { ... },
    "step_mm": 0.300
  },
  "full_steps": true
}
```

- `params.material` (NEW) — тип материала, заменяет `stone_type`
- `params.preset` (NEW) — ключ пресета из PRESET_CATALOG
- `params.stone_type` (DEPRECATED) — используйте `material`

**Response:**

```json
{
  "images": { "final": "data:image/png;base64,..." },
  "diagnostics": { ... },
  "warnings": [],
  "material_changes": [],
  "validation_warnings": []
}
```

### POST /api/process/export

Экспорт обработанного изображения в полном разрешении (BMP/PNG/TIFF).

### POST /api/process/dither-preview

Предпросмотр дизеринга. Вызывается отдельно от preview — по кнопке в UI.

---

## Vignette

### POST /api/vignette/mask

Сгенерировать маску арховой виньетки по параметрам.
