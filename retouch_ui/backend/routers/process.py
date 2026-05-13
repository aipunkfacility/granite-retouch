"""Роутер обработки изображений: загрузка, предпросмотр, экспорт."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import tempfile
import time
import uuid
from pathlib import Path
from collections import OrderedDict

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

from retouch.config import load_config, deep_merge
from retouch.processing.pipeline import (
    process_preview,
    process_steps,
    PipelineResult,
)
from retouch.processing.vignette import generate_arch_mask
from retouch.processing.export import export_result

from ..schemas import (
    UploadResponse,
    PreviewRequest,
    PreviewResponse,
    PreviewDiagnostics,
    ExportRequest,
    DitherPreviewRequest,
    DitherPreviewResponse,
    FaceOvalParams,
    PreviewParams,
    VignetteMaskRequest,
    VignetteMaskResponse,
    VignetteMaskParams,
)

logger = logging.getLogger("retouch_ui.process")

router = APIRouter(prefix="/api", tags=["process"])

# ─── Хранилище загруженных файлов ─────────────────────────────────────
# Ключ: file_id (UUID), значение: (путь к файлу, оригинальное имя, ref_count, upload_time)
_UploadedEntry = tuple[Path, str, int, float]
_uploaded_files: dict[str, _UploadedEntry] = {}

MAX_UPLOADED_FILES = 50  # A16: лимит на количество одновременно загруженных файлов
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 МБ — лимит размера загружаемого файла


def _cleanup_uploaded(file_id: str) -> None:
    """Удалить временный файл загрузки. Вызывается через BackgroundTask или TTL."""
    entry = _uploaded_files.pop(file_id, None)
    if entry is None:
        return
    path, _, _, _ = entry
    try:
        if path.exists():
            path.unlink()
            logger.debug("Удалён временный файл: %s", path)
    except OSError as exc:
        logger.warning("Не удалось удалить %s: %s", path, exc)


async def cleanup_expired() -> None:
    """Фоновая корутина: удалять файлы старше 30 минут (D.5: с учётом ref_count)."""
    MAX_AGE_SEC = 1800  # 30 минут

    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired = []
        for fid, (path, _, ref_count, upload_time) in _uploaded_files.items():
            try:
                # D.5: Файл с ref_count > 0 НЕ удаляется при TTL cleanup
                if ref_count > 0:
                    continue
                if path.exists() and (now - upload_time) > MAX_AGE_SEC:
                    expired.append(fid)
            except OSError:
                expired.append(fid)
        for fid in expired:
            _cleanup_uploaded(fid)
            logger.info("TTL-очистка: удалён file_id=%s", fid)


def _ref_inc(file_id: str) -> None:
    """D.5: Увеличить ref_count для файла."""
    entry = _uploaded_files.get(file_id)
    if entry is not None:
        path, name, ref, ts = entry
        _uploaded_files[file_id] = (path, name, ref + 1, ts)


def _ref_dec(file_id: str) -> None:
    """D.5: Уменьшить ref_count для файла."""
    entry = _uploaded_files.get(file_id)
    if entry is not None:
        path, name, ref, ts = entry
        _uploaded_files[file_id] = (path, name, max(0, ref - 1), ts)


# ─── D.6: Кэш preview ────────────────────────────────────────────────

_preview_cache: OrderedDict[str, dict] = OrderedDict()  # D.6: LRU-кэш — cache_key → {"images": dict, "diagnostics": dict, "warnings": list}
_PREVIEW_CACHE_MAX = 30  # Максимум записей в кэше


def _get_numba_available() -> bool:
    """Проверить доступность Numba для дизеринга (кешируется)."""
    try:
        from retouch.processing.export import HAS_NUMBA
        return HAS_NUMBA
    except ImportError:
        return False


def _stable_serialize(params: dict) -> str:
    """D.6: Стабильная сериализация параметров для хэша.

    Округляем float до 4 знаков → compact JSON separators → SHA256.
    _stable_serialize({a: 1.0}) == _stable_serialize({a: 1.0000})
    """
    def _round_values(obj):
        if isinstance(obj, dict):
            return {k: _round_values(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            return [_round_values(v) for v in obj]
        elif isinstance(obj, float):
            return round(obj, 4)
        return obj

    normalized = _round_values(params)
    serialized = json.dumps(normalized, separators=(',', ':'), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _cache_key(file_id: str, machine: str, params: PreviewParams | None) -> str:
    """D.6: Ключ кэша = file_id + machine + хэш параметров."""
    params_dict = params.model_dump(exclude_none=True) if params else {}
    return f"{file_id}:{machine}:{_stable_serialize(params_dict)}"


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
        content = await asyncio.wait_for(file.read(), timeout=60.0)

        # Проверка размера файла
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                413,
                f"Файл слишком большой ({len(content) / 1024 / 1024:.1f} МБ). "
                f"Максимум: {MAX_UPLOAD_BYTES // 1024 // 1024} МБ.",
            )

        tmp.write(content)
        tmp.close()  # Закрыть ДО передачи пути в PIL (Windows: PermissionError)
    except asyncio.TimeoutError:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)  # BE-L8: безопасное удаление
        raise HTTPException(408, "Превышено время загрузки файла (60 сек)")
    except HTTPException:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)  # BE-L8: безопасное удаление
        raise
    except Exception:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)  # BE-L8: безопасное удаление
        raise HTTPException(500, "Ошибка при сохранении файла")

    file_id = uuid.uuid4().hex
    # D.5: Добавляем ref_count=0 и upload_time
    _uploaded_files[file_id] = (Path(tmp.name), file.filename or "upload.png", 0, time.time())
    logger.info("Загружен файл: %s → file_id=%s", file.filename, file_id)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "upload.png",
        size_bytes=len(content),
    )


def _params_to_overrides(params: PreviewParams | None) -> tuple[dict, dict | None]:
    """Преобразовать PreviewParams в dict для deep_merge в конфиг.

    Поддерживает два формата:
    1. Полный конфиг от UI: {processing: {laser_80w: {...}}, vignette: {...}, ...}
    2. Плоские параметры: {face_oval: {...}, stone_type: "granite", step_mm: 0.3}

    E.2: Поддерживает face_oval → передача в pipeline.

    Returns:
        tuple: (overrides_dict, face_oval_dict или None)
    """
    if params is None:
        return {}, None

    overrides = {}
    p = params.model_dump(exclude_none=True)

    # face_oval → отдельный параметр (не в конфиг)
    face_oval = p.pop("face_oval", None)

    # stone_type → в секцию stone
    stone_type = p.pop("stone_type", None)
    if stone_type:
        overrides["stone"] = {"type": stone_type}

    # step_mm → в секцию machine
    step_mm = p.pop("step_mm", None)
    if step_mm:
        overrides["machine"] = {"step_mm": step_mm}

    # Вложенные секции конфига от UI (processing, vignette, stone, machine)
    # передаём напрямую — они содержат glow_size_min/max и др.
    CONFIG_SECTIONS = {"processing", "vignette", "stone", "machine"}
    for key in CONFIG_SECTIONS:
        value = p.pop(key, None)
        if value is not None and isinstance(value, dict):
            overrides[key] = value

    return overrides, face_oval


@router.post("/process/preview", response_model=PreviewResponse)
async def preview_image(
    request: PreviewRequest,
):
    """Предпросмотр обработки. Возвращает JSON с base64-картинками по шагам + диагностика."""

    # Найти загруженный файл
    entry = _uploaded_files.get(request.file_id)
    if entry is None:
        raise HTTPException(404, f"Файл не найден: {request.file_id}")

    input_path, _, _, _ = entry

    # D.6: Проверяем кэш
    cache_k = _cache_key(request.file_id, request.machine, request.params)
    cached = _preview_cache.get(cache_k)
    if cached is not None:
        # LRU: перемещаем в конец (недавно использованный)
        _preview_cache.move_to_end(cache_k)
        logger.debug("Preview cache hit: %s", cache_k)
        return PreviewResponse(**cached)

    # Собрать конфиг: загрузить полный, затем наложить params
    full_config = load_config()
    overrides_data = _params_to_overrides(request.params)
    overrides, face_oval_dict = overrides_data

    if overrides:
        full_config = deep_merge(full_config, overrides)

    # E.2: face_oval из запроса
    face_oval = face_oval_dict  # dict с cx, cy, rx, ry, source или None

    # D.3: full_steps — какие шаги возвращать
    full_steps = request.full_steps

    # D.5: Увеличиваем ref_count
    _ref_inc(request.file_id)

    # CPU-bound: запуск в отдельном потоке
    try:
        result: PipelineResult = await asyncio.wait_for(
            asyncio.to_thread(
                process_preview,
                input_path=str(input_path),
                machine_type=request.machine,
                config=full_config,
                max_size=768,
                face_oval=face_oval,
            ),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        _ref_dec(request.file_id)
        raise HTTPException(
            408,
            "Превышено время предпросмотра (45 сек). "
            "Попробуйте уменьшить размер изображения.",
        )
    except Exception as exc:
        _ref_dec(request.file_id)
        logger.exception("Ошибка предпросмотра: %s", exc)
        raise HTTPException(500, f"Ошибка обработки: {exc}")

    # D.5: Уменьшаем ref_count
    _ref_dec(request.file_id)

    # Кодируем каждый шаг в base64 data URI
    all_step_images: dict[str, Image.Image | None] = {
        "chromakey": result.img_chromakey,
        "glow": result.img_glow,
        "leveled": result.img_leveled,
        "face_corrected": result.img_face_corrected,
        "final": result.img_final,
        "arch_mask": result.arch_mask,
    }

    # D.3: При full_steps=False — только final
    step_images = all_step_images if full_steps else {"final": result.img_final}

    images: dict[str, str] = {}
    for key, img in step_images.items():
        if img is None:
            continue
        buf = io.BytesIO()
        # Конвертируем RGBA/L в RGB для корректного PNG
        if img.mode == "RGBA":
            img.save(buf, format="PNG")
        elif img.mode == "L":
            img.save(buf, format="PNG")
        else:
            img.convert("RGB").save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        images[key] = f"data:image/png;base64,{b64}"

    # Освободить память PipelineResult (после кодирования!)
    result.release_intermediates()

    diagnostics = PreviewDiagnostics(
        glow_size=result.glow_size,
        glow_opacity=result.glow_opacity,
        face_brightness_before=result.face_brightness_before,
        face_brightness_after=result.face_brightness_after,
        face_correction_factor=result.face_correction_factor,
        black_ratio=result.black_ratio,
        blue_ratio=result.blue_ratio,
        width=result.width,
        height=result.height,
        # AUDIT-3.1: передать face_oval из preview для использования в export
        face_oval=result.face_oval,
        # Numba availability — False = дизеринг на чистом Python (медленно)
        numba_available=_get_numba_available(),
    )

    response_data = {
        "images": images,
        "diagnostics": diagnostics.model_dump(),
        "warnings": result.warnings,
    }

    # D.6: Сохраняем в кэш (base64, не PIL objects) — LRU-стратегия
    if len(_preview_cache) >= _PREVIEW_CACHE_MAX:
        # Удаляем наименее недавно использованную запись (LRU)
        _preview_cache.popitem(last=False)
    _preview_cache[cache_k] = response_data

    return PreviewResponse(**response_data)


@router.post("/process/export")
async def export_image(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
):
    """Экспорт обработанного изображения в полном разрешении (BMP/PNG/TIFF)."""

    # Найти загруженный файл
    entry = _uploaded_files.get(request.file_id)
    if entry is None:
        raise HTTPException(404, f"Файл не найден: {request.file_id}")

    input_path, _, _, _ = entry

    # Собрать конфиг
    full_config = load_config()
    overrides_data = _params_to_overrides(request.params)
    overrides, face_oval_dict = overrides_data

    if overrides:
        full_config = deep_merge(full_config, overrides)

    # E.2: face_oval из запроса
    face_oval = face_oval_dict

    fmt = request.format  # "bmp", "bmp_1bit", "bmp_8bit", "png", "tiff"

    # D.5: Увеличиваем ref_count
    _ref_inc(request.file_id)

    # CPU-bound: запуск в отдельном потоке
    try:
        result: PipelineResult = await asyncio.wait_for(
            asyncio.to_thread(
                process_steps,
                input_path=str(input_path),
                machine_type=request.machine,
                config=full_config,
                face_oval=face_oval,
            ),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        _ref_dec(request.file_id)
        raise HTTPException(
            408,
            "Превышено время экспорта (60 сек). "
            "Попробуйте уменьшить размер изображения.",
        )
    except Exception as exc:
        _ref_dec(request.file_id)
        logger.exception("Ошибка экспорта: %s", exc)
        raise HTTPException(500, f"Ошибка обработки: {exc}")

    # Сохранить результат во временный файл для отдачи
    # Определяем расширение и media type по формату
    ext_map = {
        "bmp": ".bmp", "bmp_8bit": ".bmp", "bmp_1bit": ".bmp",
        "png": ".png", "tiff": ".tiff",
    }
    media_map = {
        "bmp": "image/bmp", "bmp_8bit": "image/bmp", "bmp_1bit": "image/bmp",
        "png": "image/png", "tiff": "image/tiff",
    }
    suffix = ext_map.get(fmt, ".bmp")
    media_type = media_map.get(fmt, "image/bmp")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_name = tmp.name
    tmp.close()

    try:
        if fmt in ("bmp", "bmp_1bit", "bmp_8bit"):
            # Передаём dither_method из machine_cfg
            proc_cfg = full_config.get("processing", {})
            machine_cfg = proc_cfg.get(request.machine, {})
            dither_method = machine_cfg.get("dither_method", "none")

            actual_path = export_result(
                result.img_final, tmp_name,
                machine_type=request.machine, fmt=fmt,
                dither_method=dither_method,
            )
            # export_result может вернуть другой путь (с другим расширением)
            # Если путь не совпадает — читаем из actual_path
            if actual_path != tmp_name and Path(actual_path).exists():
                tmp_name = actual_path
        elif fmt == "tiff":
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

    # D.5: Уменьшаем ref_count после завершения экспорта
    _ref_dec(request.file_id)

    filename = f"result{suffix}"
    return FileResponse(
        tmp_name,
        media_type=media_type,
        filename=filename,
        background=background_tasks,
    )


@router.post("/process/dither-preview", response_model=DitherPreviewResponse)
async def dither_preview(request: DitherPreviewRequest):
    """Предпросмотр Jarvis дизеринга для laser_80w.

    Вызывается ОТДЕЛЬНО от /process/preview — по кнопке в UI.
    Без Numba: 30-120 сек + предупреждение.
    С Numba: ~1-2 сек.
    """
    if request.machine != "laser_80w":
        raise HTTPException(400, "Дизеринг доступен только для laser_80w")

    # Найти загруженный файл
    entry = _uploaded_files.get(request.file_id)
    if entry is None:
        raise HTTPException(404, f"Файл не найден: {request.file_id}")

    input_path, _, _, _ = entry

    # Собрать конфиг
    full_config = load_config()
    overrides_data = _params_to_overrides(request.params)
    overrides, face_oval_dict = overrides_data

    if overrides:
        full_config = deep_merge(full_config, overrides)

    face_oval = face_oval_dict

    # Предупреждение о Numba
    numba_available = _get_numba_available()

    _ref_inc(request.file_id)

    # CPU-bound: полный пайплайн + дизеринг
    try:
        result: PipelineResult = await asyncio.wait_for(
            asyncio.to_thread(
                process_steps,
                input_path=str(input_path),
                machine_type=request.machine,
                config=full_config,
                face_oval=face_oval,
            ),
            timeout=180.0 if not numba_available else 30.0,
        )
    except asyncio.TimeoutError:
        _ref_dec(request.file_id)
        raise HTTPException(
            408,
            f"Превышено время дизеринг-превью ({180 if not numba_available else 30} сек).",
        )
    except Exception as exc:
        _ref_dec(request.file_id)
        logger.exception("Ошибка дизеринг-превью: %s", exc)
        raise HTTPException(500, f"Ошибка обработки: {exc}")

    _ref_dec(request.file_id)

    # Применить Jarvis дизеринг для предпросмотра
    try:
        from retouch.processing.export import jarvis_dither
        dithered = await asyncio.wait_for(
            asyncio.to_thread(jarvis_dither, result.img_final),
            timeout=120.0 if not numba_available else 10.0,
        )
    except asyncio.TimeoutError:
        result.release_intermediates()
        raise HTTPException(408, "Превышено время Jarvis дизеринга")
    except Exception as exc:
        result.release_intermediates()
        logger.exception("Ошибка Jarvis дизеринга: %s", exc)
        raise HTTPException(500, f"Ошибка дизеринга: {exc}")

    # Кодируем в base64
    buf = io.BytesIO()
    if dithered.mode == "RGBA":
        dithered.save(buf, format="PNG")
    elif dithered.mode == "L":
        dithered.save(buf, format="PNG")
    else:
        dithered.convert("RGB").save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    dithered_data_uri = f"data:image/png;base64,{b64}"

    result.release_intermediates()

    return DitherPreviewResponse(
        image=dithered_data_uri,
        numba_available=numba_available,
    )


@router.post("/vignette/mask", response_model=VignetteMaskResponse)
async def vignette_mask(request: VignetteMaskRequest):
    """Сгенерировать маску арховой виньетки по параметрам.

    Не требует загруженного изображения — только параметры виньетки и размеры.
    Используется для визуального контроля формы виньетки в Web UI (L2 overlay).
    """
    vign_cfg = request.vignette

    # Вычисляем параметры эллипса для ответа
    v_offset = request.height * vign_cfg.get("vertical_offset", 0.10)
    v_diameter = request.height * vign_cfg.get("vertical_diameter", 0.50)
    headroom = request.height * vign_cfg.get("headroom", 0.6)
    h_oversize = request.width * vign_cfg.get("horizontal_oversize", 0.2)

    arch_bottom_y = request.height - v_offset
    arch_top_y = arch_bottom_y - v_diameter - headroom

    # CPU-bound: генерация маски в отдельном потоке
    try:
        arch_mask = await asyncio.wait_for(
            asyncio.to_thread(
                generate_arch_mask,
                request.width,
                request.height,
                vign_cfg,
            ),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(408, "Превышено время генерации маски")
    except Exception as exc:
        logger.exception("Ошибка генерации маски виньетки: %s", exc)
        raise HTTPException(500, f"Ошибка генерации маски: {exc}")

    # Кодируем маску в base64 data URI
    buf = io.BytesIO()
    arch_mask.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mask_data_uri = f"data:image/png;base64,{b64}"

    return VignetteMaskResponse(
        mask=mask_data_uri,
        params=VignetteMaskParams(
            arch_top_y=arch_top_y,
            arch_bottom_y=arch_bottom_y,
            h_oversize=h_oversize,
        ),
    )
