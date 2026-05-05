"""FastAPI-бэкенд granite-retouch Web UI.

Запуск: uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8001 --reload
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from retouch import __version__

from .routers import config, presets, process
from .schemas import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("retouch_ui")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup: запустить TTL-очистку загруженных файлов
    cleanup_task = asyncio.create_task(process._ttl_cleanup())
    logger.info("granite-retouch backend v%s запущен", __version__)
    yield
    # Shutdown: отменить фоновые задачи
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("granite-retouch backend остановлен")


app = FastAPI(
    title="granite-retouch API",
    version=__version__,
    lifespan=lifespan,
)

# CORS — локальный инструмент, один оператор
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(process.router)
app.include_router(config.router)
app.include_router(presets.router)


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Проверка доступности бэкенда."""
    return HealthResponse(status="ok", version=__version__)
