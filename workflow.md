# 🎯 MEMORIAL Agentic Workflow

Добро пожаловать в систему автоматизированной подготовки портретов.

## 🚀 Как начать работу

1. **Регистрация заказа:**
   - Скопируйте файл `orders/template/order.json` в папку `orders/active/ORDER_NAME/order.json`.
   - Положите исходное фото (`source.jpg`) в ту же папку.

2. **🤖 Анализ (Analyzer Agent):**
   - Используйте навык `memorial-analyzer`.
   - Скопируйте полученный JSON в `order.json` (поле `analyzer_output`).

3. **🤖 Сборка промпта (Prompter Agent):**
   - Используйте навык `memorial-prompter`.
   - Получите готовый промпт для генерации.

4. **Генерация:**
   - Вставьте промпт в Nano Banana.
   - Сохраните результат в папку заказа.

5. **🎨 Ретушь (Photoshop):**
   - Выполните техническую обработку по [Чек-листу (.agents/postprocessing/CHECKLIST.md)](.agents/skills/memorial-postprocessing/CHECKLIST.md).

## 📂 Структура системы

- `knowledge/` — База знаний по станкам и физике гравировки.
- `prompt_blocks/` — Атомарные блоки промптов.
- `orders/` — Реестр всех заказов.
- `projects/` — Примеры выполненных работ.

---
*Система оптимизирована для Google Antigravity IDE.*
