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

### Терминал 1 — Backend (порт 8000)

Из корня проекта:

```bash
uv run uvicorn retouch_ui.backend.main:app --port 8000 --reload
```

Должен быть вывод:

```
INFO: Uvicorn running on http://127.0.0.1:8000
granite-retouch backend v3.0.0-dev запущен
```

> **Важно:** порт **8000** — по умолчанию. Vite proxy настроен на `localhost:8000`.
> Если запустите на другом порту — отредактируйте `retouch_ui/frontend/vite.config.ts` → `server.proxy.'/api'.target`.

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

Vite автоматически проксирует запросы `/api/*` на backend `localhost:8000`.

## Проверка

- Backend health: http://localhost:8000/api/health → `{"status":"ok","version":"3.0.0-dev"}`
- Frontend загружает изображение → preview → экспорт BMP/PNG/TIFF

## Production-режим (один процесс)

```bash
cd retouch_ui/frontend
npm run build                    # собирает dist/
cd ../..
uv run uvicorn retouch_ui.backend.main:app --port 8000
```

FastAPI сам раздаёт статику из `retouch_ui/frontend/dist/`.
Открывать: **http://localhost:8000**

## Типичные проблемы

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `No module named 'retouch'` | Пакет не установлен | `uv sync --extra webui` |
| `No module named 'fastapi'` | Не установлена группа webui | `uv sync --extra webui` |
| `No module named 'scipy'` | uvicorn запущен без `uv run` (системный Python) | Запускай через `uv run uvicorn ...`, не голый `uvicorn` |
| `'vite' is not recognized` | Нет node_modules | `cd retouch_ui/frontend && npm install` |
| `ECONNRESET` на `/api/*` | Backend не запущен | Запусти uvicorn (терминал 1) |
| «Загрузка превышена (30 сек)» | Vite proxy указывает на неправильный порт | Проверь `vite.config.ts`: target должен быть `http://localhost:8000` |
| `404 Not Found` на `/api/upload` | Старый URL в api.ts | Обновить код: `git pull` |
| `Frontend dist/ не найден` | Не собран фронтенд для production | `cd retouch_ui/frontend && npm run build` |

## Возможности

- Загрузка изображения через drag & drop
- Живой предпросмотр при изменении параметров (слайдеры)
- Переключение станка laser_standard / laser_80w / impact
- Пресеты (готовые наборы параметров из `presets/`)
- Экспорт BMP/PNG/TIFF в полном разрешении
- **FaceOval overlay** — интерактивная коррекция овала лица (4 drag handles). Авто-определение через профиль ширины маски (85-90% портретов), ручная корректировка для нестандартных
