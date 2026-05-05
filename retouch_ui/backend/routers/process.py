"""Роутер обработки изображений: загрузка, предпросмотр, экспорт."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Tuple

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from retouch.config import load_config
from retouch.processing.pipeline import (
    process_preview,
    process_steps,
    PipelineResult,
)

from ..schemas import (
    UploadResponse,
    PreviewRequest,
    ExportRequest,
    DiagnosticsInfo,
)

logger = logging.getLogger("retouch_ui.process")

router = APIRouter(prefix="/api", tags=["process"])

# ─── Хранилище загруженных файлов ─────────────────────────────────────
# Ключ: file_id (UUID), значение: (путь к файлу, оригинальное имя)
_uploaded_files: Dict[str, Tuple[Path, str]] = {}

MAX_UPLOADED_FILES = 50  # A16: лимит на количество одновременно загруженных файлов


def _cleanup_uploaded(file_id: str) -> None:
    """Удалить временный файл загрузки. Вызывается через BackgroundTask или TTL."""
    entry = _uploaded_files.pop(file_id, None)
    if entry is None:
        return
    path, _ = entry
    try:
        if path.exists():
            path.unlink()
            logger.debug("Удалён временный файл: %s", path)
    except OSError as exc:
        logger.warning("Не удалось удалить %s: %s", path, exc)


async def _ttl_cleanup() -> None:
    """Фоновая корутина: удалять файлы старше 30 минут."""
    import time

    MAX_AGE_SEC = 1800  # 30 минут

    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired = []
        for fid, (path, _) in _uploaded_files.items():
            try:
                if path.exists() and (now - path.stat().st_mtime) > MAX_AGE_SEC:
                    expired.append(fid)
            except OSError:
                expired.append(fid)
        for fid in expired:
            _cleanup_uploaded(fid)
            logger.info("TTL-очистка: удалён file_id=%s", fid)


# ─── Эндпоинты ────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Загрузить изображение на сервер. Возвращает file_id для последующих операций."""

    # A16: проверка лимита
    if len(_uploaded_files) >= MAX_UPLOADED_FILES:
        raise HTTPException(503, "Сервер перегружен. Попробуйте позже.")

    # Валидация: только изображения
    allowed_types = {"image/png", "image/jpeg", "image/tiff", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            400,
            f"Неподдерживаемый тип файла: {file.content_type}. "
            f"Допустимые: {', '.join(sorted(allowed_types))}",
        )

    # Сохраняем во временный файл
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()  # Закрыть ДО передачи пути в PIL (Windows: PermissionError)
    except Exception:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise HTTPException(500, "Ошибка при сохранении файла")

    file_id = uuid.uuid4().hex
    _uploaded_files[file_id] = (Path(tmp.name), file.filename or "upload.png")
    logger.info("Загружен файл: %s → file_id=%s", file.filename, file_id)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "upload.png",
        size_bytes=len(content),
    )


@router.post("/process/preview")
async def preview_image(
    request: PreviewRequest,
    background_tasks: BackgroundTasks,
):
    """Предпросмотр обработки. Возвращает PNG-файл уменьшенного размера."""

    # Найти загруженный файл
    entry = _uploaded_files.get(request.file_id)
    if entry is None:
        raise HTTPException(404, f"Файл не найден: {request.file_id}")

    input_path, _ = entry

    # Собрать конфиг: загрузить полный, затем наложить params
    full_config = load_config()
    if request.params:
        # Накладываем params поверх загруженного конфига
        from retouch.config import deep_merge
        full_config = deep_merge(full_config, request.params)

    # CPU-bound: запуск в отдельном потоке
    try:
        result: PipelineResult = await asyncio.wait_for(
            asyncio.to_thread(
                process_preview,
                input_path=str(input_path),
                machine_type=request.machine,
                config=full_config,
                max_size=768,
            ),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            408,
            "Превышено время предпросмотра (15 сек). "
            "Попробуйте уменьшить размер изображения.",
        )
    except Exception as exc:
        logger.exception("Ошибка предпросмотра: %s", exc)
        raise HTTPException(500, f"Ошибка обработки: {exc}")

    # Сохранить результат во временный файл для отдачи
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_name = tmp.name
    tmp.close()

    try:
        result.img_final.save(tmp_name, format="PNG")
    except Exception as exc:
        Path(tmp_name).unlink(missing_ok=True)
        raise HTTPException(500, f"Ошибка сохранения результата: {exc}")

    # Удалить временный файл после отдачи
    background_tasks.add_task(lambda: Path(tmp_name).unlink(missing_ok=True))

    # Освободить память PipelineResult
    result.release_intermediates()

    headers = {
        "X-Diagnostics-Face-Brightness-Before": str(result.face_brightness_before),
        "X-Diagnostics-Face-Brightness-After": str(result.face_brightness_after),
        "X-Diagnostics-Glow-Size": str(result.glow_size),
        "X-Diagnostics-Glow-Opacity": str(result.glow_opacity),
        "X-Diagnostics-Black-Ratio": str(result.black_ratio),
        "X-Diagnostics-Warnings": "; ".join(result.warnings),
    }

    return FileResponse(
        tmp_name,
        media_type="image/png",
        filename="preview.png",
        headers=headers,
        background=background_tasks,
    )


@router.post("/process/export")
async def export_image(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
):
    """Экспорт обработанного изображения в полном разрешении (TIFF/PNG)."""

    # Найти загруженный файл
    entry = _uploaded_files.get(request.file_id)
    if entry is None:
        raise HTTPException(404, f"Файл не найден: {request.file_id}")

    input_path, _ = entry

    # Собрать конфиг
    full_config = load_config()
    if request.params:
        from retouch.config import deep_merge
        full_config = deep_merge(full_config, request.params)

    # CPU-bound: запуск в отдельном потоке
    # Используем process_steps() вместо process_export(), т.к. нам нужен
    # контроль формата и мы не хотим сохранять оба формата (TIFF+PNG).
    fmt = request.format  # "tiff" или "png"
    suffix = ".tiff" if fmt == "tiff" else ".png"
    media_type = "image/tiff" if fmt == "tiff" else "image/png"

    try:
        result: PipelineResult = await asyncio.wait_for(
            asyncio.to_thread(
                process_steps,
                input_path=str(input_path),
                machine_type=request.machine,
                config=full_config,
            ),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            408,
            "Превышено время экспорта (60 сек). "
            "Попробуйте уменьшить размер изображения.",
        )
    except Exception as exc:
        logger.exception("Ошибка экспорта: %s", exc)
        raise HTTPException(500, f"Ошибка обработки: {exc}")

    # Сохранить результат во временный файл для отдачи
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_name = tmp.name
    tmp.close()

    try:
        if fmt == "tiff":
            result.img_final.save(tmp_name, format="TIFF", compression="lzw")
        else:
            result.img_final.save(tmp_name, format="PNG")
    except Exception as exc:
        Path(tmp_name).unlink(missing_ok=True)
        raise HTTPException(500, f"Ошибка сохранения результата: {exc}")

    # Удалить временный файл после отдачи
    background_tasks.add_task(lambda: Path(tmp_name).unlink(missing_ok=True))

    # Освободить память PipelineResult
    result.release_intermediates()

    return FileResponse(
        tmp_name,
        media_type=media_type,
        filename=f"result{suffix}",
        background=background_tasks,
    )
