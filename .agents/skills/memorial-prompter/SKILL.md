---
name: memorial-prompter
description: Собирает финальный промпт для генерации на основе данных из order.json и prompt_blocks.
---

# Memorial Prompter Skill

Вы — мастер промпт-инжиниринга. Ваша задача — собрать идеальный промпт для нейросети, используя блоки из папки `prompt_blocks`.

## Алгоритм работы

1. Читает `order.json` (ID заказа, тип станка, данные анализа).
2. Определяет набор блоков для сборки:
   - **Основа**: `prompt_blocks/base.md` (Role, Guidelines 0, 1, 4).
   - **Одежда**: 
     - Если в `analyzer_output` или запросе не указана ЗАМЕНА (military/civilian) -> `prompt_blocks/clothing/preserve.md`.
     - Иначе -> соответствующий блок `civilian.md` или `military.md`.
   - **Головной убор**:
     - Если нужно оставить как есть -> `prompt_blocks/headgear/preserve.md`.
     - Если нужно убрать -> `headgear/none.md`.
     - Если нужно добавить кепку -> `headgear/cap.md`.
   - **Станок**: `prompt_blocks/machine/[machine_type].md` (Технические Guideline 2, 3 и Goal).
3. Собирает промпт в следующем порядке:
   - Блок `base.md` (начало: Role/Context и Guidelines 0, 1).
   - Блок одежды.
   - Блок головного убора.
   - Блок станка (техническая часть Guidelines 2, 3).
   - Блок `base.md` (завершение: Guideline 4 и технические хвосты).
   - Блок станка (Goal).
4. Сохраняет финальный результат в `prompt.md` и обновляет `order.json`.

## Важно

Не добавляйте никакой отсебятины, используйте строго тексты из файлов блоков.
