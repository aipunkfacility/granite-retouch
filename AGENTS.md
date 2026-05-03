# AGENTS.md — Руководство для ИИ-агентов

## Обзор проекта

granite-retouch — система автоматизации подготовки промптов для генерации портретов,
предназначенных для гравировки на станках по камню (габбро/гранит).

**Важно:** Агенты генерируют только текстовые промпты для Nano Banana,
а не изображения напрямую. Генерация выполняется оператором вручную.

Основные форматы файлов:
- Markdown (.md) — документация, скилы агентов, промпт-блоки
- JSON (.json) — схемы данных, заказы

## Структура проекта

```
granite-retouch/
├── .agents/skills/              # ИИ-агенты (Antigravity Skills)
│   ├── retouch-analyzer/        # Агент анализа фото
│   ├── retouch-prompter/        # Агент создания промптов
│   │   └── prompt_blocks/       # Промпт-блоки для сборки
│   │       ├── base.md
│   │       ├── laser.md
│   │       ├── impact.md
│   │       ├── clothing/
│   │       └── headgear/
│   └── retouch-postprocessing/  # Чек-лист постобработки
├── .antigravity/                # Конфигурация Antigravity IDE
├── guides/                      # Руководства
│   ├── cli-anything-gimp.md     # Воркфлоу постобработки
│   ├── nano_banana_guide.md     # Генерация изображений
│   └── style_guide_laser.md     # Лазерный стиль
├── knowledge/                   # База знаний
│   ├── machines/                # Специфика станков
│   │   ├── laser.md             # Лазерные станки
│   │   └── impact.md            # Ударные станки
│   └── principles.md            # Принципы гравировки
├── orders/                      # Система учета заказов
│   ├── schema.json              # JSON-схема заказа
│   ├── template/                # Шаблон нового заказа
│   └── active/                  # Активные заказы
├── prepare_vignette.py          # Скрипт виньетирования
├── retouch_process.scm          # GIMP Script-Fu (запасной)
├── run_gimp.py                  # Запуск GIMP скрипта
├── AGENTS.md
├── CHANGELOG.md
├── README.md
└── workflow.md
```

## Команды

### Валидация JSON

```bash
# Проверка синтаксиса JSON (Node.js)
node -e "JSON.parse(require('fs').readFileSync('путь/к/файлу.json'))"

# Валидация по схеме (требует ajv)
npx ajv validate -s orders/schema.json -d orders/active/*/order.json
```

### Полезные команды

```bash
# Создание нового заказа (копирование шаблона)
cp orders/template/order.json orders/active/ORDER_NAME/order.json

# Линтинг Markdown (опционально)
markdownlint orders/
```

## Стиль кода

### Markdown

- **Длина строки:** 100 символов максимум
- **Язык:** русский (предпочтительно для документации)
- **Заголовки:** иерархия h1 → h2 → h3, один h1 на файл
- **Списки:** маркированные с дефисом, вложенные — 2 пробела отступа
- **Код:** обратные кавычки для команд и путей
- **Ссылки:** относительные для внутренних файлов

Пример:

```markdown
# Заголовок первого уровня

Описание раздела. Максимальная длина строки — 100 символов.

## Подраздел

- Пункт списка
  - Вложенный пункт (2 пробела)

Команда: `node -e "..."`
```

### JSON

- **Отступ:** 2 пробела
- **Кавычки:** двойные всегда
- **Trailing commas:** разрешены
- **Кодировка:** UTF-8
- **Именование ключей:** camelCase

Пример:

```json
{
  "orderId": "ORD-2026-001",
  "machineType": "laser",
  "analyzerOutput": {
    "clothingStyle": "civilian",
    "faceQuality": "good"
  }
}
```

### Файлы и папки

- **Именование:** kebab-case для файлов и папок
- **Регистр:** нижний регистр для новых файлов
- **Пробелы:** заменяются дефисами

## Работа с агентами

### retouch-analyzer

**Назначение:** Анализ исходного фото и заполнение профиля заказа.

**Входные данные:**
- Файл `source.jpg` в папке заказа

**Выходные данные:**
- Поле `analyzer_output` в `order.json`:
  - `clothingStyle` — стиль одежды
  - `fabricType` — тип ткани
  - `headgear` — головной убор
  - `faceQuality` — качество лица
  - `defects` — дефекты (массив)

**Использование:**
1. Скопировать шаблон заказа
2. Поместить source.jpg в папку заказа
3. Запустить агент для анализа
4. Скопировать результат в поле analyzer_output

### retouch-prompter

**Назначение:** Сборка финального промпта из атомарных блоков.

**Входные данные:**
- Заполненный `order.json` с `analyzer_output`
- Тип станка: `machine_type` (laser/impact)

**Выходные данные:**
- Поле `final_prompt` в `order.json`
- Готовый промпт для Nano Banana

**Структура промпта (порядок блоков):**

1. **base.md** — базовые требования (синий хромакей, разрешение)
2. **clothing/** — одежда (military, civilian, preserve)
3. **headgear/** — головной убор (none, cap, preserve)
4. **machine/** — тип станка (laser.md или impact.md)

**Важно:** Промпт должен содержать:
- Синий фон: `solid deep blue background #0000FF`
- Высокое разрешение: `8k, high resolution`
- Стиль гравировки: `engraving style, stone carving`

**Расположение блоков:** `.agents/skills/retouch-prompter/prompt_blocks/`

### retouch-postprocessing

**Назначение:** Чек-лист для технической подготовки файла в Photoshop.

**Применение:** После генерации изображения оператором.

### Постобработка изображения

Полный воркфлоу подготовки файла для гравировки:

1. **cli-anything-gimp** — преобразование в ЧБ, резкость, контраст
2. **prepare_vignette.py** — удаление хромакея, виньетирование, финальная обработка
3. Запустить: `python prepare_vignette.py -i <input> -o <output> -m <laser|impact>`
4. Проверить результат в `generated/final_vignette.tiff`

**Опционально:** GIMP-скрипт `retouch_process.scm` через `python run_gimp.py`.

**См. подробнее:** `guides/cli-anything-gimp.md`

**Обязательная проверка после обработки:**
- [ ] Фон чёрный (#000000), без градиента
- [ ] Лицо не пересвечено
- [ ] Детали волос сохранены
- [ ] Воротник чёткий
- [ ] Края плавные

> **Скрапинг ритуальных агентств** — см. [granite-crm](https://github.com/aipunkfacility/granite-crm)

## Соглашения об именовании

### Order ID

Формат: `ORD-YYYY-NNN`

Примеры:
- `ORD-2026-001`
- `ORD-2026-045`

### Папки заказов

```
orders/active/ORD-2026-001/
├── order.json           # Данные заказа
├── prompt.md            # Чистый промпт для копирования
└── generated/          # Все изображения
    ├── source.jpg           # Исходное фото
    ├── ai.png               # Нейро-ретушь (синий фон)
    ├── final_vignette.tiff  # Готовый файл (черный фон)
    └── final_vignette.png   # Превью
```

### Изображения

- Исходное фото: `source.jpg`
- Сгенерированные: `generated_001.jpg`, `generated_002.jpg`
- Финальный файл: `final.png`

## Обработка ошибок

### Валидация JSON

- Всегда проверять JSON по схеме `orders/schema.json`
- Обязательные поля: `order_id`, `machine_type`, `source_photo`, `status`
- Тип станка: только `laser` или `impact`

### Проверка SKILL.md

- Убедиться в наличии всех секций: Description, Instructions, Examples
- Проверить относительные пути в ссылках

### Тестирование промптов

1. Создать тестовый заказ в `orders/active/TEST_ORDER/`
2. Запустить полный цикл: analyzer → prompter
3. Проверить итоговый промпт вручную в Nano Banana
4. При необходимости — корректировать блоки в `.agents/skills/retouch-prompter/prompt_blocks/`

## Рекомендации по работе

### Работа с заказами

1. Всегда копировать шаблон, а не создавать с нуля
2. Заполнять все обязательные поля схемы
3. Использовать русский язык для клиентских данных
4. Статусы: new → analyzing → prompting → generating → postprocessing → done

### Работа с промптами

1. Сначала определить тип станка (laser/impact)
2. Выбрать соответствующий блок из `.agents/skills/retouch-prompter/prompt_blocks/`
3. Проверить наличие всех необходимых модификаторов
4. Добавить `engraving-ready` если станок ударный

### Работа с изображениями

1. Исходное фото должно быть хорошего качества
2. Лицо должно быть в фокусе, без размытия
3. Освещение равномерное, без глубоких теней

---

Обновлено: 2026-05-04
