---
name: retouch-prompter
description: Собирает финальный промпт для генерации на основе данных из order.json и prompt_blocks.
---

## Контекст

Ты собираешь промпт для AI-ретушёра, который генерирует изображение на синем (#0000FF)
фоне. Это изображение затем гравируется на камне.

**Принцип генерации:** Ретушь — это полная перегенерация изображения нейросетью,
а не коррекция исходного фото. Нейросеть получает исходник как референс
для идентичности и генерирует лицо, волосы, одежду, фон — с нуля, с нужными
параметрами для технологии гравировки.

**Совместимость с пайплайном:** Пайплайн программно добавляет: (1) контурный свет —
outer glow для лазера, inner glow для импакта; (2) арховую виньетку. Промпт не должен
инструктировать модель генерировать эффекты, которые пайплайн добавляет автоматически
— это создаёт двойной контур или конфликт с виньеткой.

**Хромакей:** Чистый синий (#0000FF) фон критичен для алгоритма хромакея,
отделяющего субъект от фона. Генерация градиентов, паттернов или текстур на фоне
нарушит разделение.

**Формула сепарации — ключ к пониманию всей сборки:**

- **Лазер** = тёмная обводка субъекта (в промпте) + внешний glow (добавляется
  пайплайном после генерации). Тёмный контур в лазерных блоках — это техническая
  «стена», не дающая светлым краям субъекта слиться с внешним glow в одно пятно.
- **Импакт** = только rim light / inner glow внутри силуэта (добавляется пайплайном).
  Внешнего glow нет — сепарация через контровой свет, обводящий силуэт изнутри.

Анти-кукла применяется к чертам лица — плавные тональные переходы,
без графических контуров. Это НЕ относится к контуру силуэта — там, наоборот,
нужен чёткий тональный разрыв между субъектом и фоном.

# Retouch Prompter Skill

Вы — мастер промпт-инжиниринга. Ваша задача — собрать промпт для нейросети, используя блоки из папки `prompt_blocks`, и затем консолидировать его в связный текст без дублей.

**Важно: не ищи файлы блоков.** Пути к блокам указаны ниже — читай файлы по этим путям напрямую. Не сканируй директории, не glob'ь, не grep'и. Просто читай файл по указанному пути.

## Алгоритм работы

1. Читает `order.json` из папки заказа (ID заказа, тип станка, данные анализа). Папка заказа — та, где лежит исходник.
2. Определяет набор блоков для сборки (все пути указаны от корня скилла):

   | Категория | Условие | Путь к файлу |
   |-----------|---------|-------------|
   | Основа | всегда | `prompt_blocks/base.md` |
    | Композиция | `composition_changed = true` AND `composition = "full_body"` | `prompt_blocks/composition/full-body.md` |
    | Композиция | `composition_changed = true` AND `composition = "half_body"` | `prompt_blocks/composition/half-body.md` |
    | Композиция | `composition_changed = true` AND иначе | `prompt_blocks/composition/portrait.md` |
    | Композиция | `composition_changed != true` | **блок не вставляется** |
   | Одежда | `clothing_style = "preserve"` | `prompt_blocks/clothing/preserve.md` |
   | Одежда | `clothing_style = "military"` | `prompt_blocks/clothing/military.md` |
   | Одежда | `clothing_style = "civilian"` | `prompt_blocks/clothing/civilian.md` |
    | Головной убор | `headgear = "present"` | `prompt_blocks/headgear/has-headgear.md` |
    | Головной убор | `headgear = "none"` | `prompt_blocks/headgear/none.md` |
   | Станок (тех.) | `machine_type = "laser_standard"` | `prompt_blocks/laser.md` |
   | Станок (тех.) | `machine_type = "laser_80w"` | `prompt_blocks/laser-80w.md` |
   | Станок (тех.) | `machine_type = "impact"` | `prompt_blocks/impact.md` |
    | Edge Separation | `machine_type = "laser_standard"` | `prompt_blocks/edge-separation/laser.md` |
    | Edge Separation | `machine_type = "laser_80w"` | `prompt_blocks/edge-separation/laser.md` |
   | Edge Separation | `machine_type = "impact"` | `prompt_blocks/edge-separation/impact.md` |


   Головной убор либо есть (`present`), либо нет (`none`). Тип головного убора (кепка, фуражка, платок и т.д.) не указывается — модель видит фото. Значение `composition_changed` в order.json определяет, вставляется ли composition-блок: `true` — оператор заказал изменение композиции, вставить блок; иначе — композиция не меняется, блок не вставляется (модель видит фото и воспримет фрейминг как инструкцию изменить композицию). Поле `composition_changed` заполняется анализатором (по умолчанию `false`) — оператор может переопределить на `true` при подтверждении анализа.

   Clothing-блоки содержат уникальную часть + общий фрагмент из `prompt_blocks/clothing/_shared.md`. При сборке прочитай `_shared.md` и вставь его содержимое после уникальной части clothing-блока. Для civilian-блока — не включай строку «Render all readable details from the original» (референса нет, одежда генерируется заново).
   Блок `base.md` вставляется двумя частями — до и после маркера `<!-- INSERT: COMPOSITION/CLOTHING/HEADGEAR/MACHINE -->`, см. шаг 4.
3. Подставляет данные из `analyzer_output`:
    - `garments[]` → уже содержит тональную категорию (`tone`) и перечень деталей (`details`) для каждого предмета одежды
    - Перекодируй `tone` в описание яркости естественным языком: `light` → «light gray», `medium` → «medium gray», `dark` → «dark gray», `very_dark` → «charcoal gray»
    - После clothing-блока добавь конкретизирующую строку per garment: «The [type] is [tone]. Note visible elements: [elements from details — только факт наличия, без описания внешнего вида]». Например: «The coat is charcoal gray. Note visible elements: button at center front.» — НЕ описывай внешний вид (крой, форму, текстуру), модель видит фото. Если VLM указал неточные детали (напр. «stand collar» когда стойки нет), не включай их.
    - Если `analyzer_output` пустой или отсутствует — **прекрати сборку промпта и запроси анализ**
   - `composition` → выбор composition-блока (уже учтён в шаге 2)
   - `photo_angle` + `facing_direction` → не подставляются в промпт. Если поза не меняется, base.md уже содержит «Keep the original pose and angle exactly as in the source». Если поза меняется — добавь конкретное указание после этой строки.
4. Собирает черновик промпта в следующем порядке:
   - Блок `base.md` от начала до маркера `<!-- INSERT: COMPOSITION/CLOTHING/HEADGEAR/MACHINE -->`.
   - Блок композиции.
   - Блок одежды.
    - Строка с перечнем предметов одежды из `garments[]` (шаг 3).
    - Если `body_details[]` не пуст — строка инъекции: «Body details from the source must be reproduced exactly: [location] — [description]; ... These details must be reproduced exactly as in the source photo.»
    - Блок головного убора.
   - Блок станка (техническая часть: кожа, волосы, одежда).
   - Блок `base.md` от маркера до конца (Background, Anti-Doll).


   - Блок `edge-separation/` по machine_type.
5. **Консолидация (КРИТИЧЕСКИЙ ШАГ):** Черновик содержит дубли — блоки написаны как самостоятельные документы, и при склейке одна и та же мысль повторяется в нескольких местах. Модель получает размытый сигнал от дублей. Консолидируй:
    - **Убери дословные дубли** — если одна и та же фраза встречается дважды, оставь одно вхождение там, где оно логичнее в потоке текста.
    - **Слей пересекающиеся инструкции** — если два блока говорят об одном и том же разными словами, объедини в одно предложение. Например: «The jawline matches the original photo exactly» (base) + «Keep the jawline as the sharpest tonal boundary on the lower face» (constraints) → «The jawline matches the original photo exactly — it is the sharpest tonal boundary on the lower face, with distinct brightness between face and neck.»
    - **Убери инструкции, противоречащие контексту заказа** — если `headgear = "none"` и на фото нет головного убора, не вставляй блок none.md с инструкцией «Professionally remove any headgear». Если убирать нечего — просто опиши волосы естественно.
    - **НЕ убирай усиление сигнала (signal reinforcement)** — если один и тот же эффект описан дважды разными, но непротиворечащими способами (напр. rim light: «Two light sources...» + «Add a rim light along the contour...»), это не дубль, а усиление. Оставь оба упоминания — модель лучше отрабатывает эффект, когда он описан с двух сторон.
    - **Приоритет машинных блоков над base.md** — если base.md говорит «Wrinkles are soft tonal suggestions», а impact.md говорит «Forehead wrinkles are prominent sculptural elements», машинный блок побеждает. При слиянии используй формулировку машинного блока.
    - **Таблица приоритетов при конфликтах:**

      | Конфликт | Impact | Laser | Laser 80W |
      |---|---|---|---|
      | Кожа: smooth vs tonal range | tonal range от рельефа | smooth (porcelain) | smooth base + сохранить структурные морщины |
      | Одежда: texture vs smooth | smooth fabric | texture detail | texture detail (как laser) |
      | Освещение: falloff vs even | even illumination | falloff (high-key) | directional lighting (умеренный falloff) |
      | Морщины: soft vs prominent | prominent sculptural | soft / erased | soft tonal transitions (сохранить, но не акцентировать) |
    - **Целевая длина: 20–35 строк.** Каждый абзац — одна законченная мысль. Без нумерованных секций и списков параметров.
    - **Anti-Doll** — закрывающая фраза промпта, не отдельный блок: «The portrait must look like a photograph, not an illustration — gradual tonal transitions, no harsh black stripes on skin. Work with light, not with lines.»
    - **Ограничения яркости** — один раз: «Skin must never reach pure white — only the whites of the eyes may.»
    - **Clothing stays below face brightness** — один раз, рядом с описанием одежды.
    - Проверь по чеклисту из `PROMPT_RULES.md` (файл лежит рядом с SKILL.md: `.agents/skills/retouch-prompter/PROMPT_RULES.md`).
6. Сохраняет `prompt.md` в папку заказа (там же, где исходник и `order.json`) и обновляет `order.json`.

## Важно

Блоки — исходный материал, а не готовый промпт. Черновая сборка всегда содержит дубли — это нормально, так блоки спроектированы (каждый блок самодостаточен). Шаг 5 (консолидация) — обязательный, без него модель получает размытый сигнал от повторов.
