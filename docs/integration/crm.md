# Интеграция с granite-crm

granite-retouch и granite-crm — отдельные репозитории. Связь между ними — **конвенционная**, через поле `crm_company_id` в `order.json`. Никаких API-вызовов, общих баз данных или монорепо.

---

## Как связать заказ с CRM

### При создании заказа (CLI)

```bash
python -m retouch order create ORD-2026-042 --crm CMP-0042 -m impact
```

### Вручную в order.json

```json
{
  "order_id": "ORD-2026-042",
  "crm_company_id": "CMP-0042",
  ...
}
```

Формат `crm_company_id`: `CMP-NNNN` (напр. `CMP-0042`, `CMP-0123`).

## Что даёт связь

- В `retouch order list` видно, к какой компании в CRM относится заказ
- При поиске заказа можно отследить клиента в granite-crm
- В будущем: автоматический обмен статусами через API

## Конфигурация

В `config.yaml`:

```yaml
crm:
  crm_path: "F:\\Dev\\Projects\\granite-crm"
  env_var: GRANITE_CRM_PATH
```

Или через переменную окружения:

```bash
export GRANITE_CRM_PATH="F:\Dev\Projects\granite-crm"
```

## Что НЕ делается

| Подход | Почему нет |
|--------|------------|
| API-интеграция (HTTP-запросы к Django REST) | Overkill для одного пользователя |
| Общая БД | Разные стеки, нет параллельной записи |
| Монорепо | Разные технологии (Python scripts vs Django), разные жизненные циклы |
| Синхронизация статусов | Ручной процесс устраивает |

## Будущее (если понадобится)

granite-crm уже имеет Django REST API (`/api/companies/`, `/api/orders/`). Если когда-нибудь понадобится автоматизация:

1. granite-retouch делает `POST /api/orders/` при создании заказа
2. granite-retouch делает `PATCH /api/orders/{id}/` при смене статуса
3. granite-crm подтягивает результаты

Пока это не нужно — ручной процесс работает.
