---
name: retouch-prompter
description: Собирает финальный промпт для генерации на основе данных из order.json и prompt_blocks.
---

# Retouch Prompter Skill

Вы — мастер промпт-инжиниринга. Ваша задача — собрать идеальный промпт для нейросети, используя блоки из папки `prompt_blocks`.

## Алгоритм работы

1. Читает `order.json` (ID заказа, тип станка, данные анализа).
2. Определяет набор блоков для сборки:
   - **Основа**: `prompt_blocks/base.md` (Role, Guidelines 1, 1.5, 2, 3, 4).
   - **Одежда**: 
     - Если в `analyzer_output` или запросе не указана ЗАМЕНА (military/civilian) -> `prompt_blocks/clothing/preserve.md`.
     - Иначе -> соответствующий блок `civilian.md` или `military.md`.
   - **Головной убор**:
     - Если нужно оставить как есть -> `prompt_blocks/headgear/preserve.md`.
     - Если нужно убрать -> `headgear/none.md`.
     - Если нужно добавить кепку -> `headgear/cap.md`.
   - **Станок**: прямое сопоставление по `machine_type`:
     - "laser_standard" → `prompt_blocks/laser.md`
     - "laser_80w" → `prompt_blocks/laser-80w.md`
     - "impact" → `prompt_blocks/impact.md`
   - **Запреты**: `prompt_blocks/constraints.md` (универсальные негативные ограничения, всегда включается).
3. Собирает промпт в следующем порядке:
   - Блок `base.md` (начало: Role/Context, Guidelines 1, 1.5).
   - Блок одежды.
   - Блок головного убора.
   - Блок станка (техническая часть: кожа, волосы, контраст).
   - Блок `base.md` (продолжение: Guideline 4 Anti-Doll, Guideline 2 Lighting + Brightness Ceiling, Guideline 3 Background).
   - Блок `constraints.md` (универсальные запреты).
   - Блок станка (Goal).
4. Сохраняет финальный результат в `prompt.md` и обновляет `order.json`.

## Важно

Не добавляйте никакой отсебятины, используйте строго тексты из файлов блоков.
