# Web UI — инструкция по запуску

## Требования

- **Python 3.10+** и **uv** (пакетный менеджер)
- **Node.js 18+** с **npm** (для фронтенда)

## Установка (один раз)

### 1. Python-зависимости (backend)

Из корня проекта:

```bash
uv sync --extra webui
```

Это установит пакет `granite-retouch` + FastAPI, uvicorn, pydantic, python-multipart.

### 2. Node-зависимости (frontend)

```bash
cd retouch_ui/frontend
npm install
```

## Запуск

Нужны **два терминала** — backend и frontend.

### Терминал 1 — Backend (порт 8001)

Из корня проекта:

```bash
uv run uvicorn retouch_ui.backend.main:app --port 8001 --reload
```

Должен быть вывод:

```
INFO: Uvicorn running on http://127.0.0.1:8001
granite-retouch backend v4.0.0 запущен
```

### Терминал 2 — Frontend (порт 5173)

```bash
cd retouch_ui/frontend
npm run dev
```

Должен быть вывод:

```
VITE v8.x.x  ready in ... ms
➜  Local:   http://localhost:5173/
```

## Открыть в браузере

**http://localhost:5173**

Vite автоматически проксирует запросы `/api/*` на backend `localhost:8001`.

## Проверка

- Backend health: http://localhost:8001/api/health → `{"status":"ok","version":"4.0.0"}`
- Frontend загружает изображение → preview → экспорт TIFF/PNG

## Production-режим (один процесс)

```bash
cd retouch_ui/frontend
npm run build                    # собирает dist/
cd ../..
uv run uvicorn retouch_ui.backend.main:app --port 8001
```

FastAPI сам раздаёт статику из `retouch_ui/frontend/dist/`.

## Типичные проблемы

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `No module named 'retouch'` | Пакет не установлен | `uv sync --extra webui` |
| `No module named 'fastapi'` | Не установлена группа webui | `uv sync --extra webui` |
| `'vite' is not recognized` | Нет node_modules | `cd retouch_ui/frontend && npm install` |
| `ECONNRESET` на `/api/*` | Backend не запущен | Запусти uvicorn (терминал 1) |
| `404 Not Found` на `/api/upload` | Старый URL в api.ts | Обновить код: `git pull` |
