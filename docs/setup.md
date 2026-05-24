# Установка окружения

## Требования

| Компонент | Версия | Примечание |
|-----------|--------|------------|
| Python | >= 3.10 | Проверить: `python --version` |
| uv | >= 0.4 | Менеджер пакетов Python |
| Node.js | >= 18 | Для Web UI frontend |
| npm | >= 9 | Поставляется с Node.js |

## 1. Установка uv

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

После установки **перезапустите терминал**. Проверьте:
```bash
uv --version
```

## 2. Клонирование и установка пакета

```bash
git clone https://github.com/your-org/granite-retouch.git
cd granite-retouch
```

Установка с dev-зависимостями (для тестов):
```bash
uv sync --extra dev
```

Установка с Web UI:
```bash
uv sync --extra webui
```

Всё вместе:
```bash
uv sync --extra dev --extra webui
```

После `uv sync` создаётся виртуальное окружение `.venv/`. Активация:

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (Git Bash):**
```bash
source .venv/Scripts/activate
```

**Linux/macOS:**
```bash
source .venv/bin/activate
```

> Если активация не удалась на Windows PowerShell — выполните `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 3. Проверка установки

```bash
# Все тесты (460+ тестов + 31 backend API тест)
.venv\Scripts\python.exe -m pytest tests/ -v

# Справка CLI
.venv\Scripts\python.exe -m retouch --help
```

Или через Makefile (если доступен `make`):
```bash
make test      # запустить все тесты
make install   # установить пакет
```

## 4. Web UI

### Frontend (Node.js)

```bash
cd retouch_ui/frontend
npm install
npm run dev        # dev-сервер на http://localhost:5173
```

### Backend (FastAPI)

```bash
# Из корня проекта
uv run uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8000 --reload --workers 1
```

### Всё сразу

```bash
make ui            # dev-режим (backend + frontend)
make ui-prod       # production (один процесс uvicorn)
```

## 5. Быстрый запуск (без Web UI)

```bash
# Создать заказ
uv run python -m retouch order create ORD-2026-042 -m impact

# Обработка портрета
uv run python -m retouch process -i ai.png -o final.bmp -m laser_standard
```

## 6. Установка GIMP (опционально)

Для экспериментального GIMP-пайплайна:
- Скачайте GIMP 2.10+ с [gimp.org](https://www.gimp.org/downloads/)
- Убедитесь, что `gimp` доступен в PATH

## 7. Numba (опционально, для ускорения)

```bash
uv sync --extra fast
```

Ускоряет дизеринг в 10-50x.

## Частые проблемы

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `'uv' не найден` | uv не установлен | Установите через irm/curl (шаг 1) |
| `No module named 'retouch'` | Пакет не установлен | `uv sync --extra dev` |
| `No module named 'fastapi'` | Нет webui зависимостей | `uv sync --extra webui` |
| `'vite' is not recognized` | Нет node_modules | `cd retouch_ui/frontend && npm install` |
| `SSL certificate verify failed` | Корпоративный прокси | `set SSL_CERT_FILE=path/to/cert.pem` |
