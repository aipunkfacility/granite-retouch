# Схема заказа — order.json

Описание всех полей `order.json`. Схема валидации: `orders/schema.json`.

---

## Обязательные поля

| Поле | Тип | Pattern | Описание |
|------|-----|---------|----------|
| `order_id` | string | `^ORD-\d{4}-\d{3}$` | Идентификатор заказа (напр. `ORD-2026-042`) |
| `machine_type` | enum | `laser_standard`, `laser_80w`, `impact` | Тип гравировального станка |
| `source_photo` | string | — | Имя файла исходного фото (напр. `source.jpg`) |
| `status` | enum | см. ниже | Текущий статус заказа |

### Статусы

```
new → analyzing → prompting → generating → postprocessing → done
```

## Опциональные поля

| Поле | Тип | Описание |
|------|-----|----------|
| `crm_company_id` | string | ID компании в granite-crm. Формат: `CMP-NNNN` (напр. `CMP-0042`). Пустая строка = нет привязки |
| `machine_model` | string | Модель станка (напр. `Mirtels L60120`) |
| `final_prompt` | string | Финальный промпт для Nano Banana |
| `generated_image` | string | Путь к сгенерированному изображению |
| `final_file` | string | Путь к готовому файлу для станка |
| `notes` | string | Заметки к заказу |
| `created_at` | string | Дата создания (ISO 8601) |
| `face_oval` | object | Ручная коррекция овала лица (этап E). Если указан — используется вместо автоматической детекции |

## client

Информация о клиенте.

| Поле | Тип | Описание |
|------|-----|----------|
| `name` | string | Имя клиента |
| `contact` | string | Контакт (телефон / email / Telegram) |

## analyzer_output

Результат работы агента `retouch-analyzer`. Заполняется после анализа фото.

| Поле | Тип | Enum | Описание |
|------|-----|------|----------|
| `clothing_style` | string | `civilian`, `military`, `preserve` | Факт + дефолт: `military` = военная (сохранить), `preserve` = гражданская (сохранить), `civilian` = заменить (оператор) |
| `headgear` | string | `none`, `present` | Факт + дефолт: `present` = есть (сохранить), `none` = нет |
| `composition` | string | `portrait`, `half_body`, `full_body` | Состав кадра — выбор composition-блока |
| `composition_changed` | boolean | `true`, `false` | `true` = оператор заказал изменение композиции → вставить composition-блок. `false` (по умолчанию) = не вставлять |
| `photo_angle` | string | `frontal`, `3/4`, `profile` | Ракурс фото — для Source Angle Preservation |
| `facing_direction` | string | `left`, `right`, `center` | Направление взгляда — для Source Angle Preservation |
| `garments` | array | minItems: 1 | Список предметов одежды с тональной рекодировкой (минимум 1) |
| `garments[].tone` | string | `light`, `medium`, `dark`, `very_dark` | Тональная категория → диапазон яркости |
| `garments[].type` | string | — | Тип предмета на английском |
| `garments[].details` | [string] | minItems: 1 | Перечень видимых деталей на английском (минимум 1) |

## face_oval

Ручная коррекция овала лица (этап E). Если указан — используется вместо автоматической детекции.

| Поле | Тип | Описание |
|------|-----|----------|
| `cx` | float | Центр овала по X (0–1, нормализованный) |
| `cy` | float | Центр овала по Y (0–1, нормализованный) |
| `rx` | float | Радиус овала по X (0–1, нормализованный) |
| `ry` | float | Радиус овала по Y (0–1, нормализованный) |
| `source` | string | Источник: `"heuristic"` (автоматический) или `"manual"` (пользовательский) |

Пример:
```json
{
  "face_oval": {
    "cx": 0.5,
    "cy": 0.25,
    "rx": 0.15,
    "ry": 0.20,
    "source": "manual"
  }
}
```

## postprocessing

| Поле | Тип | Описание |
|------|-----|----------|
| `gimp_processed` | string | Путь к файлу после GIMP-обработки |

---

## Пример заполненного заказа

```json
{
  "order_id": "ORD-2026-001",
  "crm_company_id": "CMP-0042",
  "client": {
    "name": "Иванов Иван Иванович",
    "contact": "+7-999-123-45-67"
  },
  "machine_type": "laser_standard",
  "machine_model": "Mirtels L60120",
  "source_photo": "source.jpg",
  "status": "done",
  "analyzer_output": {
    "clothing_style": "military",
    "headgear": "present",
    "composition": "portrait",
    "composition_changed": false,
    "photo_angle": "3/4",
    "facing_direction": "right",
    "garments": [
      {
        "tone": "light",
        "type": "dress shirt",
        "details": ["collar", "button placket", "vertical weave"]
      },
      {
        "tone": "very_dark",
        "type": "uniform jacket",
        "details": ["lapels", "shoulder boards", "three medals on left chest"]
      }
    ]
  },
  "final_prompt": "Professional retouched portrait...",
  "generated_image": "generated/ai.png",
  "final_file": "generated/final.bmp",
  "created_at": "2026-05-01T10:00:00+07:00",
  "notes": "Военный, нужен контурный свет 60px"
}
```

## Структура директории заказа

```
orders/active/ORD-2026-001/
├── order.json           # Данные заказа
├── prompt.md            # Промпт для Nano Banana
├── source.jpg           # Исходное фото клиента
└── generated/
    ├── ai.png           # Нейро-ретушь (синий фон)
    ├── final.bmp       # Готовый файл (чёрный фон)
    └── final.png        # Превью
```
