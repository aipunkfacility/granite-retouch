# granite-retouch Makefile
# Удобные шорткаты для повседневных операций

PYTHON ?= uv run python
RETOUCH := uv run python -m retouch

.PHONY: install install-dev process validate gimp test lint clean \
	ui-backend ui-frontend ui ui-install ui-force-install ui-build ui-prod

# --- Установка ---

install:
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev]"

# --- Обработка ---

process: ## Pillow-обработка: make process I=input.png O=output.tiff M=laser
	$(RETOUCH) process -i $(I) -o $(O) -m $(M)

validate: ## Валидация: make validate I=input.png
	$(RETOUCH) validate -i $(I)

gimp: ## GIMP-обработка: make gimp I=input.png O=output.tiff M=impact
	$(RETOUCH) gimp -i $(I) -o $(O) -m $(M)

# --- Тесты ---

test:
	$(PYTHON) -m pytest tests/ -v

# --- Очистка ---

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf *.egg-info/ dist/ build/

# --- Web UI ===

ui-backend:      ## Запустить FastAPI backend
	uv run uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8000 --reload --workers 1

ui-frontend:     ## Запустить Vite frontend
	cd retouch_ui/frontend && npm run dev

ui: ui-install   ## Запустить backend + frontend (авто-установка зависимостей)
	cd retouch_ui/frontend && npx concurrently -n backend,frontend -c blue,green \
	        "uv run uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8000 --workers 1" \
	        "npm run dev"
	# ⚠ concurrently — devDependency (-D). При NODE_ENV=production npm может не установить devDependencies.
	# ui-install проверяет наличие node_modules — это защищает от проблемы.
	# Для production используйте `make ui-prod` (не нужен concurrently).

ui-install:      ## Установить зависимости frontend (только если node_modules отсутствует)
	@if [ ! -d "retouch_ui/frontend/node_modules" ]; then \
	        echo "Installing frontend dependencies..."; \
	        cd retouch_ui/frontend && npm install; \
	else \
	        echo "Frontend dependencies already installed. Run 'make ui-force-install' to reinstall."; \
	fi

ui-force-install: ## Принудительная переустановка зависимостей frontend
	cd retouch_ui/frontend && npm install

ui-build: ui-install  ## Сборка frontend для продакшена
	cd retouch_ui/frontend && npm run build

ui-prod: ui-build     ## Production: собрать статику + запустить uvicorn (один процесс)
	uv run uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8000 --workers 1

# --- Справка ---

help:
	@echo "granite-retouch commands:"
	@echo "  make install          — установить пакет"
	@echo "  make install-dev      — установить с dev-зависимостями"
	@echo "  make process          — Pillow-обработка (I= M= O=)"
	@echo "  make validate         — валидация изображения (I=)"
	@echo "  make gimp             — GIMP-обработка (I= O= M=)"
	@echo "  make test             — запустить тесты"
	@echo "  make clean            — очистить кэш Python"
	@echo "  make ui               — запустить backend + frontend (dev-режим)"
	@echo "  make ui-backend       — запустить FastAPI backend (dev-режим)"
	@echo "  make ui-frontend      — запустить Vite frontend (dev-режим)"
	@echo "  make ui-install       — установить зависимости frontend"
	@echo "  make ui-build         — сборка frontend для продакшена"
	@echo "  make ui-prod          — production: статики + uvicorn (один процесс)"
