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
| `clothing_style` | string | `civilian`, `military`, `preserve` | Стиль одежды |
| `fabric_type` | string | — | Тип ткани (шерсть, хлопок, рип-стоп, кожа) |
| `headgear` | string | `none`, `cap`, `preserve` | Головной убор |
| `face_quality` | string | `high`, `medium`, `low` | Качество лица на фото |
| `defects` | [string] | — | Массив дефектов (noise, low contrast, cracks, etc.) |

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
    "fabric_type": "ripstop",
    "headgear": "cap",
    "face_quality": "medium",
    "defects": ["noise", "low contrast"]
  },
  "final_prompt": "Professional retouched portrait...",
  "generated_image": "generated/ai.png",
  "final_file": "generated/final.tiff",
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
    ├── final.tiff       # Готовый файл (чёрный фон)
    └── final.png        # Превью
```
