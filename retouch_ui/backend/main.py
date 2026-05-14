"""FastAPI-бэкенд granite-retouch Web UI.

Запуск: uv run python -m uvicorn retouch_ui.backend.main:app --host 127.0.0.1 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from retouch import __version__

from .routers import config, material, presets, process
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
    cleanup_task = asyncio.create_task(process.cleanup_expired())
    logger.info("granite-retouch backend v%s запущен", __version__)

    # AUDIT-8.4: Прогрев Numba JIT — первый экспорт с дизерингом
    # не будет зависать 2-10 сек на компиляции
    await _warmup_numba_jit()

    yield
    # Shutdown: отменить фоновые задачи
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("granite-retouch backend остановлен")


async def _warmup_numba_jit():
    """AUDIT-8.4: Прогрев Numba JIT-компиляции для дизеринга.

    Первый вызов _error_diffusion_dither_jit компилируется 2-10 сек.
    Прогрев на крошечном изображении (8x8) — компиляция та же, но
    выполнение мгновенное. Последующие вызовы используют кеш.
    """
    try:
        from retouch.processing.export import _error_diffusion_dither
        from PIL import Image

        tiny_img = Image.new("L", (8, 8), 128)

        def _warmup():
            _error_diffusion_dither(tiny_img, [(1, 0, 7/48), (2, 0, 5/48)])

        await asyncio.to_thread(_warmup)
        logger.info("Numba JIT warmup complete")
    except Exception as exc:
        logger.warning("Numba JIT warmup failed (non-critical): %s", exc)


app = FastAPI(
    title="granite-retouch API",
    version=__version__,
    lifespan=lifespan,
)

# CORS — локальный инструмент, один оператор.
# Явный список origins вместо "*" — корректная работа с credentials-запросами
# (спецификация запрещает Access-Control-Allow-Credentials при origin "*").
ALLOWED_ORIGINS = [
    "http://localhost:5173",    # Vite dev server
    "http://localhost:3000",    # альтернативный dev-порт
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,     # API не использует cookies/auth
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(process.router)
app.include_router(config.router)
app.include_router(presets.router)
app.include_router(material.router)


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Проверка доступности бэкенда."""
    return HealthResponse(status="ok", version=__version__)

# ВАЖНО: StaticFiles монтируется ПОСЛЕДНИМ — все /api/* роуты имеют приоритет.
# Новые роуты ДОЛЖНЫ использовать префикс /api, иначе будут перехвачены StaticFiles.
_dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="static")
else:
    logger.warning(
        "Frontend dist/ не найден (%s). Production-роутинг отключен. "
        "Запустите `make ui-build` для сборки статики.",
        _dist_dir,
    )
