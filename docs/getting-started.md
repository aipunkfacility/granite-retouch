# Быстрый старт

Полный цикл от заказа до готового файла за 5 шагов.

---

## 1. Создать заказ

```bash
python -m retouch order create ORD-2026-042 --crm CMP-0042 -m impact
```

Это создаст директорию `orders/active/ORD-2026-042/` с `order.json` и подпапкой `generated/`.

Флаги:
- `--crm CMP-0042` — привязка к компании в granite-crm (опционально)
- `-m impact` — тип станка: `laser_standard` (по умолчанию), `laser_80w` или `impact`

Альтернатива: создать вручную, скопировав `orders/template/order.json`.

## 2. Положить исходное фото

Скопируйте фото клиента в директорию заказа:

```
orders/active/ORD-2026-042/source.jpg
```

## 3. Анализ (retouch-analyzer)

Используйте навык `retouch-analyzer` в Antigravity IDE.

Результат: поле `analyzer_output` в `order.json` заполняется данными о фото — тип одежды, головной убор, качество лица, дефекты.

См. `.agents/skills/retouch-analyzer/SKILL.md`.

## 4. Сборка промпта (retouch-prompter)

Используйте навык `retouch-prompter` в Antigravity IDE.

Результат: файл `prompt.md` в директории заказа + поле `final_prompt` в `order.json`.

См. `.agents/skills/retouch-prompter/SKILL.md`.

## 5. Генерация + ретушь

### 5a. Генерация (Nano Banana)

Вставьте промпт из `prompt.md` в Nano Banana Pro. Сохраните результат как:

```
orders/active/ORD-2026-042/generated/ai.png
```

Требование: фон — строго синий хромакей `#0000FF`.

См. [guides/nano-banana.md](guides/nano-banana.md).

### 5b. Ретушь (CLI)

```bash
python -m retouch process -i orders/active/ORD-2026-042/generated/ai.png \
    -o orders/active/ORD-2026-042/generated/final.bmp -m laser_standard

# Для мощного лазера 60-80W+
python -m retouch process -i orders/active/ORD-2026-042/generated/ai.png \
    -o orders/active/ORD-2026-042/generated/final.bmp -m laser_80w
```

Результат: `final.bmp` (8-bit grayscale для станка) + `final.png` (превью). Для laser_80w: `final.bmp` (1-bit монохром с дизерингом Floyd-Steinberg).

### 5c. Проверка результата

| Проверка | Описание |
|----------|----------|
| Фон чёрный | Абсолютно чёрный (#000000), без градиента |
| Лицо не пересвечено | Видны тени под глазами, на щеках |
| Детали волос | Сохранены пряди, объём |
| Воротник | Чёткий, контрастный, без пересвета |
| Края плавные | Виньетка — плавный переход |
| Голова видна целиком | Виньетка не обрезает верхнюю часть |

Если результат не устраивает — настройте параметры в `config.yaml` и повторите шаг 5b.

См. [reference/config.md](reference/config.md) и [guides/vignette.md](guides/vignette.md).

---

## Web UI — интерактивная настройка

Для подбора параметров с живым предпросмотром используйте Web UI:

```bash
make ui
```

Это запустит FastAPI backend (порт 8000) и Vite frontend (порт 5173). Откройте http://localhost:5173 в браузере.

Возможности Web UI:
- Загрузка изображения через drag & drop
- Живой предпросмотр при изменении параметров (слайдеры)
- Переключение станка laser_standard / laser_80w / impact
- Пресеты (готовые наборы параметров)
- Экспорт BMP/PNG/TIFF в полном разрешении

Для production-режима (один процесс):

```bash
make ui-prod
```

---

## Управление заказами

```bash
# Список всех заказов
python -m retouch order list

# Валидация заказа
python -m retouch order validate ORD-2026-042

# Создать с привязкой к CRM
python -m retouch order create ORD-2026-043 --crm CMP-0012 -m laser_standard
```

См. [reference/cli.md](reference/cli.md).
