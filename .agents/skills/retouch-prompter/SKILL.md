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

Анти-кукла (Guideline 4) применяется к чертам лица — плавные тональные переходы,
без графических контуров. Это НЕ относится к контуру силуэта — там, наоборот,
нужен чёткий тональный разрыв между субъектом и фоном.

# Retouch Prompter Skill

Вы — мастер промпт-инжиниринга. Ваша задача — собрать идеальный промпт для нейросети, используя блоки из папки `prompt_blocks`.

## Алгоритм работы

1. Читает `order.json` из папки заказа (ID заказа, тип станка, данные анализа). Папка заказа — та, где лежит исходник.
2. Определяет набор блоков для сборки:
   - **Основа**: `prompt_blocks/base.md` (Role/Context, Guidelines 1, 1.5, 2 Lighting + Brightness Ceiling, 2.5 Source Angle Preservation, 3 Background, 4 Anti-Doll).
   - **Композиция**:
     - Если `analyzer_output.composition` = `"full_body"` → `prompt_blocks/composition/full-body.md`.
     - Если `analyzer_output.composition` = `"half_body"` → `prompt_blocks/composition/half-body.md`.
     - Иначе → `prompt_blocks/composition/portrait.md`.
   - **Одежда**:
     - Если `analyzer_output.clothing_style` = `"preserve"` → `prompt_blocks/clothing/preserve.md`.
     - Если `analyzer_output.clothing_style` = `"military"` → `prompt_blocks/clothing/military.md`.
     - Если `analyzer_output.clothing_style` = `"civilian"` → `prompt_blocks/clothing/civilian.md`.
   - **Головной убор**:
     - Если `analyzer_output.headgear` = `"cap"` → `prompt_blocks/headgear/cap.md`.
     - Если `analyzer_output.headgear` = `"none"` → `prompt_blocks/headgear/none.md`.
     - Значение `preserve` больше не существует — головной убор либо есть (`cap`), либо нет (`none`).
   - **Станок**: прямое сопоставление по `machine_type`:
     - "laser_standard" → `prompt_blocks/laser.md`
     - "laser_80w" → `prompt_blocks/laser-80w.md`
     - "impact" → `prompt_blocks/impact.md`
   - **Edge Separation**: прямое сопоставление по `machine_type`:
     - "laser_standard" → `prompt_blocks/edge-separation/laser.md`
     - "laser_80w" → `prompt_blocks/edge-separation/laser-80w.md`
     - "impact" → `prompt_blocks/edge-separation/impact.md`
   - **Запреты**: `prompt_blocks/constraints.md` (универсальные негативные ограничения, всегда включается).
3. Подставляет данные из `analyzer_output`:
   - `garments[]` → уже содержит тональную категорию (`tone`) и перечень деталей (`details`) для каждого предмета одежды
   - Перекодируй `tone` в диапазон яркости: `light` → light gray (brightness 160–220), `medium` → medium gray (100–159), `dark` → dark gray (50–99), `very_dark` → charcoal gray (20–49)
   - Если `analyzer_output` пустой или отсутствует — **прекрати сборку промпта и запроси анализ**
   - `composition` → выбор composition-блока (уже учтён в шаге 2)
   - `photo_angle` + `facing_direction` → подставь вместо `{{ANGLE_DIRECTIVE}}` в base.md (Guideline 2.5) по маппингу:
     - `"frontal"` → `facing the camera directly`
     - `"3/4"` + `facing_direction: "right"` → `3/4 view, slightly turned to the right`
     - `"3/4"` + `facing_direction: "left"` → `3/4 view, slightly turned to the left`
     - `"profile"` + `facing_direction: "right"` → `profile view, facing right`
     - `"profile"` + `facing_direction: "left"` → `profile view, facing left`
     - `facing_direction: "center"` не добавляет направления (используется только с `frontal`)
4. Собирает промпт в следующем порядке:
   - Блок `base.md` (Role/Context, Guidelines 1, 1.5, 2 Lighting + Brightness Ceiling, 2.5 Source Angle Preservation).
   - Блок композиции.
   - Блок одежды.
   - Блок головного убора.
   - Блок станка (техническая часть: кожа, волосы, одежда).
   - Блок `base.md` (продолжение: Guideline 3 Background, Guideline 4 Anti-Doll).
   - Блок `constraints.md` (универсальные запреты).
   - Блок `edge-separation/` по machine_type (laser.md / laser-80w.md / impact.md).
   - Блок станка (Goal).
5. Сохраняет `prompt.md` в папку заказа (там же, где исходник и `order.json`) и обновляет `order.json`.

## Важно

Не добавляйте никакой отсебятины, используйте строго тексты из файлов блоков.
