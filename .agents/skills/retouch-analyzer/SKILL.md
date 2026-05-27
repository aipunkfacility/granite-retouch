---
name: retouch-analyzer
description: Анализирует исходное фото для гравировки на памятниках и возвращает структурированный JSON.
---

# Retouch Analyzer Skill

Проанализируй исходное фото и заполни `analyzer_output` в `order.json`. Результат используется `retouch-prompter` для сборки промпта.

## Контекст

Ты анализируешь фото для гравировки на камне. Ретушь — полная перегенерация изображения нейросетью. Твои данные определяют:
- Какие блоки промпта собираются (`clothing_style` → выбор clothing-блока, `headgear` → выбор headgear-блока, `composition` → выбор composition-блока)
- Как перекодируются тона одежды (`garments[].tone` → тональная рекодировка в Clothing Tonal Rule)
- Какие детали одежды модель должна сгенерировать (`garments[].details` → перечень деталей)
- Какой ракурс сохранять (`photo_angle` → Source Angle Preservation)
- Направление взгляда (`facing_direction` → уточнение ракурса в Source Angle Preservation)

## Алгоритм анализа

0. **Спроси оператора** перед анализом:
   - **Тип станка?** — `laser_standard` / `laser_80w` / `impact`. С фото тип станка не определить, а от него зависит: rim light (impact) или контур (laser). Записать в `order.json` как `machine_type`.
   - Проанализируй фото → автодетектируй `clothing_style` и `headgear`.
   - **Предложи оператору подтвердить или переопределить** стиль одежды (`military` / `preserve` / `civilian`) и головной убор (`cap` / `none`).
   - Запиши результат в `order.json` в папку заказа (там же, где исходник). Если `order.json` не существует — создай.

1. **Определи** состав кадра (`composition`):
   - Голова и плечи → `"portrait"`
   - Виден до пояса (торс, но не ниже) → `"half_body"`
   - Видно ниже пояса → `"full_body"`

2. **Определи** ракурс (`photo_angle`):
   - Лицо обращено прямо к камере → `"frontal"`
   - Лицо развёрнуто примерно на 30–60° → `"3/4"`
   - Видно только один глаз / половина лица → `"profile"`

2.5 **Определи** направление взгляда (`facing_direction`):
   - Лицо обращено прямо к камере → `"center"`
   - Лицо развёрнуто влево (со стороны зрителя) → `"left"`
   - Лицо развёрнуто вправо (со стороны зрителя) → `"right"`
   - **Логика:** направление определяется со стороны зрителя, смотрящего на фото. Если правая щека видна больше → `facing_direction: "left"` (человек смотрит влево от зрителя).
   - **Жёсткое правило:** при `photo_angle: "frontal"` → `facing_direction` **всегда** `"center"`. Не анализируй направление — фронтальный ракурс по определению не имеет поворота.

3. **Определи** стиль одежды (`clothing_style`):
   - На фото военная форма (погоны, знаки различия, медали) → `"military"`
   - Гражданская одежда → `"preserve"`
   - **Логика:** анализатор определяет факт и ставит дефолт = сохранить. `military` = сохранить военную форму (нужен military-блок промпта). `preserve` = оставить гражданскую одежду как есть. Если оператор хочет заменить военную форму на гражданскую → он меняет значение на `"civilian"`. Анализатор НЕ принимает это решение.

4. **Определи** головной убор (`headgear`):
   - Кепка, фуражка, берет → `"cap"`
   - Нет головного убора → `"none"`
   - **Логика:** значение по умолчанию = сохранить то, что на фото. Если головной убор есть → `cap` (сохранить), нет → `none`. Если оператор хочет убрать головной убор → он меняет на `"none"`. Если хочет добавить → на `"cap"`. Анализатор НЕ принимает это решение.

5. **Проанализируй** каждый предмет одежды отдельно (`garments`):
   - Ищи отдельные предметы: рубашка, пиджак, жилет, галстук, шарф и т.д.
   - Для каждого предмета определи:
     - **`tone`** — тональная категория по шкале яркости 0–255:
       - Белая / очень светлая одежда → `"light"` (в промпте станет: light gray, brightness 160–220)
       - Средне-серая одежда → `"medium"` (medium gray, brightness 100–159)
       - Тёмная одежда → `"dark"` (dark gray, brightness 50–99)
       - Очень тёмная / чёрная одежда → `"very_dark"` (charcoal gray, brightness 20–49)
     - **`type`** — тип предмета на английском (dress shirt, blazer, tie, vest, uniform jacket и т.д.)
     - **`details`** — перечень видимых деталей на английском, минимум 1 деталь (collar, lapels, buttons, pocket flaps, shoulder boards, medals, collar insignia, embroidery, stitching, fold shadows и т.д.)
   - **Жёсткое правило:** одежда не ярче лица. Если рубашка на фото белая → `tone: "light"`, не `"medium"` — промптер перекодирует её в light gray (160–220), а не оставит белой (240–255).

6. **Собери** JSON и запиши в `analyzer_output` поля `order.json`.

## Формат вывода

Верни ТОЛЬКО валидный JSON, соответствующий схеме `analyzer_output` в `orders/schema.json`.

Пример — мужчина в белой рубашке и чёрном пиджаке с медалями:

```json
{
  "clothing_style": "military",
  "headgear": "none",
  "composition": "portrait",
  "photo_angle": "3/4",
  "facing_direction": "right",
  "garments": [
    {
      "tone": "light",
      "type": "dress shirt",
      "details": ["collar", "button placket", "vertical weave", "fold shadows"]
    },
    {
      "tone": "very_dark",
      "type": "uniform jacket",
      "details": ["lapels", "shoulder boards", "collar insignia", "three medals on left chest"]
    }
  ]
}
```

Контрпример — мужчина в чёрном пиджаке (без светлой одежды):

❌ Неправильно:
```json
{
  "garments": [
    {"tone": "light", "type": "shirt", "details": ["collar"]},
    {"tone": "very_dark", "type": "blazer", "details": ["lapels"]}
  ]
}
```
→ `tone: "light"` указан, но светлой рубашки на фото нет — модель попытается найти белую рубашку.

✅ Правильно:
```json
{
  "garments": [
    {"tone": "very_dark", "type": "blazer", "details": ["lapels", "shoulder seam", "pocket flaps"]}
  ]
}
```
→ Только предметы, реально видимые на фото.

Контрпример — женщина в светлой блузке:

```json
{
  "clothing_style": "preserve",
  "headgear": "none",
  "composition": "portrait",
  "photo_angle": "frontal",
  "facing_direction": "center",
  "garments": [
    {
      "tone": "light",
      "type": "blouse",
      "details": ["round collar", "button front", "fabric drape", "subtle folds"]
    }
  ]
}
```
