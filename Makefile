# granite-retouch Makefile
# Удобные шорткаты для повседневных операций

PYTHON ?= python
RETOUCH := $(PYTHON) -m retouch

.PHONY: install install-dev process validate gimp test lint clean

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

# --- Справка ---

help:
	@echo "granite-retouch commands:"
	@echo "  make install      — установить пакет"
	@echo "  make install-dev  — установить с dev-зависимостями"
	@echo "  make process      — Pillow-обработка (I= M= O=)"
	@echo "  make validate     — валидация изображения (I=)"
	@echo "  make gimp         — GIMP-обработка (I= O= M=)"
	@echo "  make test         — запустить тесты"
	@echo "  make clean        — очистить кэш Python"
