# Возможности агента — Granite Retouch

**granite-retouch** — система автоматизации подготовки промптов для генерации портретов,
предназначенных для гравировки на станках по камню (габбро/гранит).

> **OpenCode** — CLI-ориентированная IDE для ИИ-агентов. Конфигурация проекта в
> `opencode.json`. Skills сканируются из `.agents/skills/` (настроено в `skills.paths`).
> MCP-серверы запускаются при старте opencode (`enabled: true`).

---

## Структура конфигурации

```
granite-retouch/
├── opencode.json              # MCP + skills.paths
├── .agents/skills/            # Skills проекта — коммитятся в git
│   ├── retouch-analyzer/      # Анализ фото → JSON
│   ├── retouch-prompter/      # Сборка промпта из блоков
│   ├── retouch-postprocessing/ # Чек-лист Photoshop (CHECKLIST.md)
│   ├── brainstorming/         # Superpowers
│   ├── systematic-debugging/  # Superpowers
│   ├── test-driven-development/ # Superpowers
│   ├── writing-plans/         # Superpowers
│   └── ... (всего 14 superpowers)
├── retouch/                   # Python-модуль обработки
│   ├── processing/            # 11 модулей пайплайна
│   └── cli.py                 # CLI entrypoint
└── docs/                      # Документация
```

> **Project vs Global scope:**
> `.agents/skills/` — только для этого проекта, коммитится в git.
> `~/.config/opencode/skills/` — глобальные скиллы OpenCode для всех проектов.

---

## Superpowers

Набор дисциплинирующих навыков из [Superpowers](https://github.com/obra/superpowers)
установлен в `.agents/skills/`. OpenCode загружает их автоматически через
`skills.paths` в `opencode.json`.

**Активация:** использовать нативный `skill` инструмент OpenCode для загрузки скилла.

---

## MCP-серверы

Настраиваются в `opencode.json`, секция `mcp`. Стартуют автоматически при запуске
opencode.

| Сервер | Пакет | Для чего используется |
| :--- | :--- | :--- |
| **Context7** | [`@upstash/context7-mcp`](https://github.com/upstash/context7) | Актуальная документация библиотек: Python 3.14, Pillow, NumPy, FastAPI, Pydantic, SQLAlchemy. Предотвращает галлюцинации устаревшего API. |
| **Sequential Thinking** | [`@modelcontextprotocol/server-sequential-thinking`](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking) | Пошаговое планирование перед сложными задачами: рефакторинг пайплайна, оптимизация дизеринга, добавление нового модуля обработки. |

**Конфигурация `opencode.json`:**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "skills": {
    "paths": [".agents/skills"]
  },
  "mcp": {
    "context7": {
      "type": "local",
      "command": ["npx", "-y", "@upstash/context7-mcp@latest"],
      "enabled": true
    },
    "sequentialthinking": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-sequential-thinking"],
      "enabled": true
    }
  }
}
```

---

## Skills проекта

Каждый skill — папка с `SKILL.md` в `.agents/skills/`. OpenCode читает
`name` + `description` из frontmatter при старте, полные инструкции подгружаются
только при активации.

### retouch-analyzer

**Путь:** `.agents/skills/retouch-analyzer/SKILL.md`

Анализирует исходное фото и возвращает структурированный JSON: стиль одежды,
головной убор, состав кадра, ракурс, направление взгляда, перечень предметов
одежды с тональной рекодировкой и деталями. Результат используется
`retouch-prompter` для сборки промпта.

**Активируется:** "проанализируй фото", "заполни analyzer_output", "анализ
изображения".

```bash
# Анализ через CLI (если нужна автоматическая метрика)
uv run python -m retouch process -i input.png -o final.bmp --dry-run
```

**Формат вывода — JSON** в `analyzer_output`:
```json
{
  "clothing_style": "military",
  "headgear": "present",
  "composition": "portrait",
  "photo_angle": "3/4",
  "facing_direction": "right",
  "garments": [
    {
      "tone": "light",
      "type": "dress shirt",
      "details": ["collar", "button placket", "vertical weave"]
    },
    {
      "tone": "very_dark",
      "type": "uniform jacket",
      "details": ["lapels", "shoulder boards", "three medals on left chest"]
    }
  ]
}
```

### retouch-prompter

**Путь:** `.agents/skills/retouch-prompter/SKILL.md`

Собирает финальный промпт для Nano Banana из блоков
(`prompt_blocks/base.md`, `clothing/`, `headgear/`, `laser.md`, `laser-80w.md`,
`impact.md`, `edge-separation/`) на основе `order.json`.

**Активируется:** "собери промпт", "сформируй prompt.md", "финальный промпт".

**Порядок сборки:**
1. `base.md` (Role/Context, Guidelines 1, 1.5, 2 Lighting, 2.5 Source Angle Preservation)
2. Блок композиции (portrait / half-body / full-body)
3. Блок одежды (preserve / civilian / military)
4. Блок головного убора (none / present)
5. Блок станка (техническая часть: кожа, волосы, одежда)
6. `base.md` (продолжение: Guideline 3 Background, Guideline 4 Anti-Doll)

8. `edge-separation/` по machine_type (laser / laser-80w / impact)
9. Блок станка (Goal)

### retouch-postprocessing

**Путь:** `.agents/skills/retouch-postprocessing/CHECKLIST.md`

> **Примечание:** не содержит `SKILL.md` — загружается вручную по запросу.

Чек-лист ручной постобработки в Photoshop: подготовка Ч/Б, вырезка фона,
контурный свет (Inner Glow), Levels, Unsharp Mask, экспорт BMP/TIFF.

**Использовать когда:** нужно провести постобработку сгенерированного изображения
перед отправкой на станок.

---

## Быстрые команды

```bash
# Обработка портрета
uv run python -m retouch process -i ai.png -o final.bmp -m laser_standard
uv run python -m retouch process -i ai.png -o final.bmp --preset graver5-impact

# Управление заказами
uv run python -m retouch order create ORD-2026-042 --crm CMP-0042 -m impact
uv run python -m retouch order list
uv run python -m retouch order validate ORD-2026-042

# Тесты (266+ автотестов + 31 backend API)
make test

# Web UI
make ui              # dev: backend + frontend
make ui-backend      # только FastAPI backend
make ui-frontend     # только Vite frontend
make ui-prod         # production
```

---

## Использование Superpowers

| Навык | Когда использовать |
| :--- | :--- |
| **test-driven-development** | При реализации фич и багфиксов. Сначала тест, потом код. |
| **systematic-debugging** | При любых ошибках. Поиск Root Cause обязателен. |
| **writing-plans** | Перед любой задачей сложнее 5 минут. Разбиение на атомарные шаги. |
| **brainstorming** | В начале работы над задачей для уточнения требований. |
| **verification-before-completion** | Перед утверждением что работа завершена. |

---

## Маршрутизация задач

```
Запрос пользователя
        │
        ├─ "проанализируй фото / заполни анализ"
        │   └─ retouch-analyzer → изучает фото → JSON в order.json
        │
        ├─ "собери промпт / сформируй prompt.md"
        │   └─ retouch-prompter → читает order.json → собирает блоки → prompt.md
        │
        ├─ "постобработка / photoshop / чек-лист"
        │   └─ retouch-postprocessing → CHECKLIST.md → ручные шаги
        │
        ├─ "баг / ошибка / тест упал"
        │   └─ systematic-debugging → Context7 MCP для API → root cause
        │
        ├─ "сделать / реализовать / написать код"
        │   └─ test-driven-development → Context7 MCP → тест → код
        │
        └─ "спланировать / распиши шаги"
            └─ writing-plans → sequentialthinking MCP → пошаговый план
```

---

## Соглашения

- **Order ID:** `ORD-YYYY-NNN` (напр. `ORD-2026-042`)
- **CRM Company ID:** `CMP-NNNN` (напр. `CMP-0042`)
- **Типы станков:** `laser_standard`, `laser_80w`, `impact` (+ пресет `graver5-impact`)
- **Папки заказов:** `orders/active/ORD-YYYY-NNN/`
- **Язык документации:** русский
- **Длина строки в markdown:** 100 символов максимум

---

*Версия: 1.0 · Дата: 2026-05-20*
*IDE: OpenCode · Документация: https://opencode.ai*
