# Фаза 0: Рефакторинг пайплайна

**Версия плана**: 3.4
**Предыдущий этап**: [Pre-0](dev-plan-pre0-quickfixes.md)
**Следующий этап**: [Фаза 1](dev-plan-phase1-backend.md)
**Время**: 4–6 часов
**Цель**: Расщепить монолитный `process()` на компонуемые шаги с доступом к промежуточным результатам. Без этого Web UI не может работать.

---

## Контекст проблемы

Текущий `process()` делает всё: валидирует, обрабатывает, сохраняет файлы, печатает в stdout. Это блокирует:
- Предпросмотр без сохранения файлов
- Доступ к промежуточным этапам (chromakey, glow, levels)
- Параллельную обработку запросов

---

## Breaking Changes

> ⚠ Внимание: эта фаза меняет сигнатуры функций. Все Breaking Changes собраны здесь.

| Функция | Было | Стало | Влияние |
|---------|------|-------|---------|
| `check_face_brightness()` | Возвращает `Image` | Возвращает `(Image, float, float, float)` | test_levels.py — обновить все вызовы |
| `load_config()` | Возвращает yaml как есть | `deep_merge(DEFAULTS, yaml)` — частичный yaml дополняется дефолтами | Может изменить поведение при частичном config.yaml |
| `process()` | Монолит с I/O | Тонкая обёртка над `process_export()` | CLI не ломается (обратная совместимость сохранена) |

---

## Затрагиваемые файлы

| Файл | Изменение |
|------|-----------|
| `retouch/processing/pipeline.py` | Основной рефакторинг: +PipelineResult, +process_steps, +process_preview, +process_export, +img.close() после chromakey |
| `retouch/processing/__init__.py` | Добавить публичные экспорты |
| `retouch/processing/levels.py` | Заменить print() на logging, добавить face_region_top, вынести highlight_start, **изменить возвращаемое значение check_face_brightness()**, **исправить псевдокод subject_mask_arr (A4)** |
| `retouch/config.py` | Добавить deep_merge() с deepcopy, Pydantic-модель (optional import), убрать version drift, **+ face_region_top и highlight_start в DEFAULTS (A1)** |
| `config.yaml` | **+ face_region_top и highlight_start для laser и impact (A1)** |
| `retouch/cli.py` | Адаптировать под новый API + logging.basicConfig |
| `tests/test_levels.py` | Обновить вызовы check_face_brightness() под новую сигнатуру |
| `tests/test_pipeline.py` | Обновить под новый API |

**Без изменений**: chromakey.py, glow.py, vignette.py — их API уже чистый.

---

## Задача 1: PipelineResult dataclass

**Файл**: `retouch/processing/pipeline.py`

```python
from dataclasses import dataclass, field
from PIL import Image

@dataclass
class PipelineResult:
    """Результат пайплайна — все промежуточные этапы + диагностика."""

    # Промежуточные изображения (PIL.Image | None после release_intermediates)
    img_chromakey: Image.Image | None       # После хромакея (RGBA)
    img_gray: Image.Image | None            # После конвертации в L
    img_glow: Image.Image | None            # После Inner Glow (L)
    img_leveled: Image.Image | None         # После Levels + Unsharp (L)
    img_face_corrected: Image.Image | None  # После face brightness correction (L)
    img_final: Image.Image                  # После виньетки (RGB) — всегда сохраняется
    arch_mask: Image.Image | None           # Маска виньетки (L)
    subject_mask: Image.Image | None        # Маска субъекта (L)

    # Диагностика
    glow_size: int
    glow_opacity: float
    face_brightness_before: float
    face_brightness_after: float
    face_correction_factor: float
    black_ratio: float
    blue_ratio: float
    width: int
    height: int
    warnings: list[str] = field(default_factory=list)

    def release_intermediates(self):
        """Освободить память от промежуточных изображений.
        После вызова доступ к img_chromakey, img_gray, img_glow, img_leveled,
        img_face_corrected, arch_mask, subject_mask вернёт None.
        img_final остаётся доступным — он нужен для сохранения."""
        self.img_chromakey = None
        self.img_gray = None
        self.img_glow = None
        self.img_leveled = None
        self.img_face_corrected = None
        self.arch_mask = None
        self.subject_mask = None
```

> **A15**: Docstring `release_intermediates()` явно описывает, какие поля становятся `None`, и подчёркивает, что `img_final` остаётся доступным.

---

## Задача 2: process_steps()

**Файл**: `retouch/processing/pipeline.py`

Новый API — «чистый» пайплайн без I/O:

```python
import logging

logger = logging.getLogger(__name__)


def process_steps(
    input_path: str,
    machine_type: str = "laser",
    config: dict | None = None,
    glow_size_override: int | None = None,
    glow_opacity_override: float | None = None,
    no_validate: bool = False,
) -> PipelineResult:
    """Полный пайплайн с доступом к каждому шагу.

    Не сохраняет файлы. Не печатает в stdout.
    Возвращает PipelineResult со всеми промежуточными изображениями и диагностикой.

    Raises:
        FileNotFoundError: input_path не существует
        ValueError: невалидное изображение или конфиг
    """
    if config is None:
        config = load_config()

    # Валидация конфига
    warnings = validate_config(config)

    # Валидация входного изображения
    validate_image_input(input_path, config)

    # Загрузка
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size

    # Валидация хромакея
    proc_cfg = config.get("processing", {})
    threshold = proc_cfg.get("blue_threshold", 30)
    min_blue_ratio = proc_cfg.get("min_blue_ratio", 0.15)
    if not no_validate:
        validate_blue_chromakey(img, threshold=threshold, min_blue_ratio=min_blue_ratio)

    # 1. Хромакей
    fringe_radius = proc_cfg.get("fringe_radius", 3)
    img_chromakey, subject_mask = remove_blue_background(
        img, threshold=threshold, fringe_radius=fringe_radius
    )

    # A2: Закрыть исходное изображение — файловый дескриптор и память больше не нужны.
    # После remove_blue_background() результат в img_chromakey, исходный img не используется.
    img.close()

    # 2. Grayscale
    img_gray = img_chromakey.convert("L")

    # 3. Inner Glow
    # ВАЖНО: имена параметров — glow_size_override / glow_opacity_override
    # (соответствуют текущей сигнатуре apply_inner_glow в glow.py)
    machine_cfg = proc_cfg.get(machine_type, {})
    img_glow, glow_size, glow_opacity = apply_inner_glow(
        img_gray, subject_mask, machine_cfg,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
    )

    # 4. Levels + Unsharp
    brightness_factor = machine_cfg.get("brightness", 1.0)
    img_leveled = apply_levels(img_glow, brightness_factor=brightness_factor)
    img_leveled = apply_unsharp_mask(img_leveled)

    # 5. Face brightness correction
    # Breaking Change: check_face_brightness теперь возвращает кортеж
    face_target = machine_cfg.get("face_brightness_target", [200, 230])
    face_region_top = machine_cfg.get("face_region_top", 0.45)
    highlight_start = machine_cfg.get("highlight_start", 200)
    img_face_corrected, face_before, face_after, correction_factor = check_face_brightness(
        img_leveled, face_target, subject_mask,
        glow_size=glow_size,
        face_region_top=face_region_top,
        highlight_start=highlight_start,
    )

    # 6. Vignette
    vign_cfg = config.get("vignette", {})
    img_final, arch_mask = apply_vignette(img_face_corrected, width, height, vign_cfg)

    # 7. Валидация результата
    # ВАЖНО: передаём img_final, а не Image.new — иначе валидация всегда 100%
    black_ratio = 0.0
    blue_ratio = 0.0
    if not no_validate:
        result_min_black = config.get("result_min_black_ratio", 0.25)
        black_ratio = validate_result_black_ratio(img_final, min_black_ratio=result_min_black)
        # Blue ratio — из img_chromakey (исходное img уже закрыто — A2)
        blue_ratio = sum(1 for p in img_chromakey.getdata() if p[2] > threshold) / (width * height)

    logger.info(
        "Pipeline complete: %dx%d, glow=%dpx/%.0f%%, face=%.0f→%.0f",
        width, height, glow_size, glow_opacity * 100, face_before, face_after,
    )

    return PipelineResult(
        img_chromakey=img_chromakey,
        img_gray=img_gray,
        img_glow=img_glow,
        img_leveled=img_leveled,
        img_face_corrected=img_face_corrected,
        img_final=img_final,
        arch_mask=arch_mask,
        subject_mask=subject_mask,
        glow_size=glow_size,
        glow_opacity=glow_opacity,
        face_brightness_before=face_before,
        face_brightness_after=face_after,
        face_correction_factor=correction_factor,
        black_ratio=black_ratio,
        blue_ratio=blue_ratio,
        width=width,
        height=height,
        warnings=warnings,
    )
```

**Ключевые отличия от текущего process():**
- Нет `print()` — только `logging`
- Нет сохранения файлов
- Нет `output_path` в параметрах
- Возвращает структурированный `PipelineResult`
- **A2**: `img.close()` вызывается СРАЗУ после `remove_blue_background()` — файловый дескриптор и память освобождаются
- `face_region_top` и `highlight_start` читаются из конфига (A1)
- `highlight_start` передаётся в `check_face_brightness()`
- `validate_result_black_ratio` вызывается на `img_final`, **не на `Image.new`**
- Параметры `apply_inner_glow` — `glow_size_override`/`glow_opacity_override` (в точности как в текущей сигнатуре glow.py)
- Blue ratio вычисляется из `img_chromakey`, т.к. исходное `img` уже закрыто

---

## Задача 3: process_preview() — с ресайзом

**Файл**: `retouch/processing/pipeline.py`

```python
import tempfile
from pathlib import Path


def process_preview(
    input_path: str,
    machine_type: str = "laser",
    config: dict | None = None,
    max_size: int = 768,
    **kwargs,
) -> PipelineResult:
    """Предпросмотр — уменьшенная копия для Web UI.

    1. Загружает полное изображение ОДИН раз (A5)
    2. Уменьшает до max_size по длинной стороне (thumbnail), если нужно
    3. Сохраняет уменьшенное во временный файл (дескриптор закрыт ДО записи — Windows-safe)
    4. Вызывает process_steps() на уменьшенном
    5. Возвращает PipelineResult (все картинки уменьшенные)

    Glow фиксируется на середине диапазона для стабильности preview:
    glow_size = (glow_size_min + glow_size_max) // 2
    """
    if config is None:
        config = load_config()

    machine_cfg = config.get("processing", {}).get(machine_type, {})

    # Фиксируем glow для стабильного preview
    glow_min = machine_cfg.get("glow_size_min", 40)
    glow_max = machine_cfg.get("glow_size_max", 80)
    glow_mid = (glow_min + glow_max) // 2

    opacity_min = machine_cfg.get("glow_opacity_min", 30)
    opacity_max = machine_cfg.get("glow_opacity_max", 40)
    opacity_mid = (opacity_min + opacity_max) / 2 / 100.0

    # A5: Открываем изображение ОДИН раз — решаем, нужен ли ресайз,
    # тут же делаем thumbnail, сохраняем, закрываем.
    img = Image.open(input_path)
    needs_resize = max(img.size) > max_size
    tmp_path = None

    try:
        if needs_resize:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
            # Создаём временный файл, сразу закрываем дескриптор (Windows-safe)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp_name = tmp.name
            tmp.close()  # Закрыть дескриптор ДО записи — иначе PermissionError на Windows
            img.save(tmp_name, format="PNG")
            img.close()  # Освободить дескриптор после записи
            tmp_path = tmp_name
            work_path = tmp_path
        else:
            img.close()  # Освободить дескриптор даже когда ресайз не нужен
            work_path = input_path

        return process_steps(
            input_path=work_path,
            machine_type=machine_type,
            config=config,
            glow_size_override=glow_mid,
            glow_opacity_override=opacity_mid,
            **kwargs,
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
```

**Ключевые отличия от v3.3 (A5):**
- Изображение открывается **один раз** вместо двух
- `img.thumbnail()` выполняется в памяти — не нужно переоткрывать файл
- `img.close()` вызывается в обеих ветках: и при ресайзе, и без него
- Нет «открыть → закрыть → переоткрыть» — один `Image.open()` решает всё

---

## Задача 4: process_export()

**Файл**: `retouch/processing/pipeline.py`

```python
from pathlib import Path


def process_export(
    input_path: str,
    output_path: str,
    machine_type: str = "laser",
    config: dict | None = None,
    **kwargs,
) -> PipelineResult:
    """Полная обработка + сохранение TIFF/PNG (текущее поведение CLI).

    Вызывает process_steps(), затем сохраняет результат.
    Промежуточные изображения освобождаются для экономии памяти.
    """
    result = process_steps(
        input_path=input_path,
        machine_type=machine_type,
        config=config,
        **kwargs,
    )

    # Сохранение TIFF + PNG
    tiff_path = output_path
    png_path = str(Path(output_path).with_suffix(".png"))  # Безопасная замена расширения
    result.img_final.save(tiff_path, format="TIFF", compression="lzw")
    result.img_final.save(png_path, format="PNG")

    logger.info(f"Сохранено: {tiff_path}, {png_path}")

    # Освобождаем промежуточные для экономии RAM
    result.release_intermediates()
    return result
```

---

## Задача 5: Обратная совместимость — process()

**Файл**: `retouch/processing/pipeline.py`

```python
def process(input_path, output_path, machine_type="laser",
            glow_size_override=None, glow_opacity_override=None,
            config=None):
    """Обратная совместимая обёртка. CLI не ломается."""
    return process_export(
        input_path=input_path,
        output_path=output_path,
        machine_type=machine_type,
        config=config,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
    )
```

---

## Задача 6: Замена print() на logging + basicConfig

**Файлы**: `retouch/processing/pipeline.py`, `retouch/processing/levels.py`, `retouch/cli.py`

В начале каждого файла:
```python
import logging
logger = logging.getLogger(__name__)
```

Замены:

| Было | Стало |
|------|-------|
| `print("DEBUG face BEFORE glow/brightness")` | `logger.debug("Face brightness check: before correction")` |
| `print(f"Face brightness: {avg:.1f} → target {target_min}-{target_max}")` | `logger.info("Face brightness: %.1f → target %d-%d", avg, target_min, target_max)` |
| `print(f"Applied curves correction: factor={correction:.3f}")` | `logger.info("Curves correction: factor=%.3f", correction)` |
| Любой другой `print()` | `logger.debug()` или `logger.info()` |

**ВАЖНО**: Без `basicConfig` логгер молчит. Добавить в `retouch/cli.py`:

```python
import logging

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    # ... остальной код CLI ...
```

И в `retouch/__main__.py`:
```python
from .cli import main
main()
```

---

## Задача 7: deep_merge в load_config() — с deepcopy

**Файл**: `retouch/config.py`

```python
import copy


def deep_merge(base: dict, override: dict) -> dict:
    """Рекурсивно сливает override в base. override побеждает.
    base копируется глубоко (deepcopy) — мутация результата не затрагивает оригинал."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def find_config_path() -> Path | None:
    """Найти config.yaml. Единая точка поиска для CLI и backend."""
    candidates = [
        Path(__file__).parent.parent / "config.yaml",
        Path.cwd() / "config.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_config(config_path=None):
    """Загрузить конфиг: YAML с deep-merge поверх DEFAULTS.
    DEFAULTS копируется глубоко — мутация результата не мутирует DEFAULTS.
    Поиск config_path делегирован find_config_path()."""
    defaults = copy.deepcopy(DEFAULTS)

    if config_path is None:
        config_path = find_config_path()

    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f) or {}
        return deep_merge(defaults, yaml_config)

    return defaults
```

**Критические отличия от текущего load_config():**
- `copy.deepcopy(base)` вместо `base.copy()` — мутация результата **не затрагивает** DEFAULTS
- `copy.deepcopy(DEFAULTS)` в `load_config` — каждый вызов получает свежую копию
- Частичный yaml корректно дополняется дефолтами
- `find_config_path()` — единая точка поиска для CLI и backend

---

## Задача 8: Pydantic-модель конфига — conditional import

**Файл**: `retouch/config.py`

Pydantic — optional зависимость. Без неё `validate_config` работает через dict-проверки:

```python
try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


if HAS_PYDANTIC:
    class MachineConfig(BaseModel):
        glow_size_min: int = Field(40, ge=5, le=100)
        glow_size_max: int = Field(80, ge=5, le=100)
        glow_opacity_min: int = Field(30, ge=10, le=100)
        glow_opacity_max: int = Field(40, ge=10, le=100)
        brightness: float = Field(1.18, ge=0.5, le=1.5)
        face_brightness_target: list[int] = Field([230, 245])
        face_region_top: float = Field(0.45, ge=0.2, le=0.8)       # A1
        highlight_start: int = Field(200, ge=100, le=250)           # A1

    class ProcessingConfig(BaseModel):
        blue_threshold: int = Field(30, ge=10, le=80)
        min_blue_ratio: float = Field(0.15, ge=0.0, le=1.0)
        fringe_radius: int = Field(3, ge=0, le=10)
        laser: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=40, glow_size_max=80, glow_opacity_min=30, glow_opacity_max=40,
            brightness=1.18, face_brightness_target=[230, 245]))
        impact: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=10, glow_size_max=25, glow_opacity_min=60, glow_opacity_max=80,
            brightness=1.00, face_brightness_target=[185, 210]))

    class VignetteConfig(BaseModel):
        vertical_offset: float = Field(0.10, ge=0.0, le=0.3)
        vertical_diameter: float = Field(0.50, ge=0.2, le=0.8)
        blur_radius: int = Field(60, ge=10, le=120)
        headroom: float = Field(0.6, ge=0.2, le=1.0)
        horizontal_oversize: float = Field(0.2, ge=0.0, le=0.5)

    class RetouchConfig(BaseModel):
        processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
        vignette: VignetteConfig = Field(default_factory=VignetteConfig)
        model_config = {"extra": "allow"}


def validate_config(config: dict) -> list[str]:
    """Валидация конфига. Возвращает список предупреждений.
    Использует Pydantic если доступен, иначе — dict-проверки."""
    warnings = []

    if HAS_PYDANTIC:
        try:
            RetouchConfig(**config)
        except Exception as e:
            warnings.append(f"Config validation: {e}")

    # Кросс-валидация (Pydantic не проверяет отношения полей)
    for machine in ("laser", "impact"):
        mc = config.get("processing", {}).get(machine, {})
        if mc.get("glow_size_min", 0) > mc.get("glow_size_max", 0):
            warnings.append(f"processing.{machine}: glow_size_min > glow_size_max")
        if mc.get("glow_opacity_min", 0) > mc.get("glow_opacity_max", 0):
            warnings.append(f"processing.{machine}: glow_opacity_min > glow_opacity_max")

    return warnings
```

**A1**: `face_region_top` и `highlight_start` теперь присутствуют в `MachineConfig` — один источник истины для дефолтов и диапазонов.

**`pyproject.toml`** — Pydantic как optional dependency:
```toml
[project.optional-dependencies]
webui = ["pydantic>=2.0", "fastapi>=0.110.0", "uvicorn[standard]>=0.29.0", "python-multipart>=0.0.9"]
```

---

## Задача 9: check_face_brightness() — новый возврат + face_region_top + исправленный псевдокод (A4)

**Файл**: `retouch/processing/levels.py`

### Breaking Change: возвращаемое значение

```python
import logging

logger = logging.getLogger(__name__)


def check_face_brightness(img, face_target, subject_mask, glow_size=0,
                          face_region_top=0.45, highlight_start=200):
    """Проверить и скорректировать яркость лица.

    Breaking Change: теперь возвращает кортеж (img, before, after, factor).
    Ранее возвращала только img.

    Args:
        img: PIL.Image в режиме L (grayscale)
        face_target: [min, max] целевого диапазона яркости
        subject_mask: PIL.Image в режиме L (маска субъекта)
        glow_size: размер inner glow — на столько пикселей сжимаем маску
        face_region_top: доля высоты изображения, в которой замеряется яркость.
            0.45 = верхние 45% картинки (голова без плеч).
        highlight_start: значение (0-255), выше которого коррекция затухает.
            Вынесено из хардкода 200 в параметр конфига.
    """
    # Сжать маску чтобы исключить glow-зону из замера
    if glow_size > 0:
        inner_mask_img = _shrink_mask(subject_mask, glow_size)
    else:
        inner_mask_img = subject_mask

    if HAS_NUMPY:
        arr = np.array(img, dtype=np.float32)

        # A4: Правильная последовательность — сначала np.array от маски,
        # потом обрезка верхней части для зоны лица
        subject_mask_arr = np.array(subject_mask)
        mask_arr = np.array(inner_mask_img)

        # Ограничиваем зону замера верхней частью (лицо без плеч)
        h = img.height
        cutoff = int(h * face_region_top)
        face_region = subject_mask_arr.copy()
        face_region[cutoff:, :] = 0  # Обнуляем нижнюю часть

        inner_mask = face_region > 128
        if inner_mask.sum() == 0:
            # fallback на полную маску (без обрезки по высоте)
            inner_mask = subject_mask_arr > 128

        inner_pixels = arr[inner_mask]
        if len(inner_pixels) == 0:
            # Нет пикселей субъекта — вернуть без изменений
            return img, 0.0, 0.0, 1.0

        avg_brightness = float(inner_pixels.mean())
    else:
        from PIL import ImageStat
        stat = ImageStat.Stat(img, mask=inner_mask_img)
        avg_brightness = stat.mean[0]
        # Без numpy face_region_top не применяется — fallback на полную маску

    target_min, target_max = face_target
    target_mid = (target_min + target_max) / 2

    logger.info("Face brightness: %.1f → target %d-%d", avg_brightness, target_min, target_max)

    if avg_brightness < target_min or avg_brightness > target_max:
        correction = target_mid / max(avg_brightness, 1)
        correction = max(0.60, min(1.40, correction))

        if HAS_NUMPY:
            # Нелинейная коррекция: тени поднимаются, света нет
            result_arr = _curves_correction(arr, correction, highlight_start=highlight_start)
            result = Image.fromarray(result_arr.astype(np.uint8), "L")
        else:
            # Pillow fallback — простая линейная коррекция (хуже, но работает)
            enhancer = ImageEnhance.Brightness(img)
            result = enhancer.enhance(correction)

        # Проверяем результат на внутренней маске
        if HAS_NUMPY:
            result_arr = np.array(result, dtype=np.float32)
            new_avg = float(result_arr[inner_mask].mean())
            logger.info("Curves correction: factor=%.3f, %.1f → %.1f", correction, avg_brightness, new_avg)
        else:
            new_avg = target_mid
            logger.info("Linear correction: factor=%.3f, %.1f → %.1f", correction, avg_brightness, new_avg)

        # ВАЖНО: возврат кортежа вместо одного Image
        return result, float(avg_brightness), float(new_avg), float(correction)

    logger.info("Face brightness OK, no correction needed")
    return img, float(avg_brightness), float(avg_brightness), 1.0
```

### A4: Что исправлено в псевдокоде

В v3.3 псевдокод использовал `subject_mask_arr` без определения. Теперь:
1. `subject_mask_arr = np.array(subject_mask)` — **явное определение** перед использованием
2. `face_region = subject_mask_arr.copy()` — копия массива маски
3. `face_region[cutoff:, :] = 0` — обнуляем нижнюю часть
4. `inner_mask = face_region > 128` — булева маска зоны лица
5. `if inner_mask.sum() == 0: inner_mask = subject_mask_arr > 128` — fallback на полную маску

### Обновление test_levels.py

Все вызовы `check_face_brightness` нужно обновить:

```python
# Было:
result = check_face_brightness(img, target, mask)

# Стало:
result, before, after, factor = check_face_brightness(img, target, mask)
```

### highlight_start — вынести из хардкода

```python
def _curves_correction(arr, correction, highlight_start=200.0):
    """Кривая коррекции: полная в тенях, затухающая в светах.
    highlight_start: значение (0-255), выше которого коррекция затухает.
    """
    h = highlight_start / 255.0
    # ... существующая логика с h вместо захардкоженного 200/255 ...
    norm = arr / 255.0

    # Weight: 1.0 для теней, 0.0 для светов
    weight = np.where(
        norm < h,
        1.0,
        np.clip(1.0 - (norm - h) / (1.0 - h), 0, 1)
    )

    # Линейная коррекция: pixel * correction
    linear = arr * correction

    # Разница: насколько линейная коррекция меняет пиксель
    delta = linear - arr

    # Применяем delta с weight — тени полностью, света минимально
    result = arr + delta * weight

    return np.clip(result, 0, 255)
```

---

## Задача 10: Публичные экспорты processing/__init__.py

**Файл**: `retouch/processing/__init__.py`

```python
"""Модуль обработки изображений granite-retouch."""

from .pipeline import process, process_steps, process_preview, process_export, PipelineResult

__all__ = [
    "process",
    "process_steps",
    "process_preview",
    "process_export",
    "PipelineResult",
]
```

---

## Задача 11: Интеграционный CLI-тест

**Файл**: `tests/test_cli_integration.py` (новый)

```python
"""Интеграционный тест: CLI работает как subprocess."""
import subprocess
import tempfile
from pathlib import Path
from PIL import Image


def test_cli_process_creates_output():
    """retouch process создаёт TIFF + PNG файлы."""
    # Создаём синтетическое изображение с хромакеем
    img = Image.new("RGBA", (512, 512), (0, 0, 255, 255))  # синий фон
    for x in range(200, 312):
        for y in range(200, 312):
            img.putpixel((x, y), (255, 255, 255, 255))

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.png"
        output_path = Path(tmp) / "output.tif"
        img.save(input_path)

        result = subprocess.run(
            ["python", "-m", "retouch", "process",
             str(input_path), str(output_path), "--machine", "laser"],
            capture_output=True, text=True, timeout=30,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_path.exists(), "TIFF not created"
        png_path = Path(tmp) / "output.png"
        assert png_path.exists(), "PNG not created"
```

---

## Задача 11.5: find_config_path() — подтверждение интеграции

**Файл**: `retouch/config.py`

> **Примечание**: `find_config_path()` уже определена в задаче 7 вместе с `load_config()`.
> Эта подзадача — напоминание агенту убедиться, что `find_config_path()` экспортирована
> и доступна для backend (Фаза 1).

**Проверка**:
```python
# Убедиться, что find_config_path доступна извне:
from retouch.config import find_config_path
path = find_config_path()
assert path is None or isinstance(path, Path)
```

---

## Задача 12: Обновление test_levels.py и test_pipeline.py

**Файл**: `tests/test_levels.py`

Все вызовы `check_face_brightness` обновить под новый возврат:

```python
# Было:
result_img = check_face_brightness(img, target, mask, glow_size=10)

# Стало:
result_img, before, after, factor = check_face_brightness(img, target, mask, glow_size=10)
```

**Полный пример обновления теста**:

```python
class TestCheckFaceBrightness:
    """Тесты контроля яркости лица."""

    def test_dark_face_gets_brightened(self):
        """Тёмное лицо (среднее 80) корректируется вверх."""
        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 255)  # всё — субъект
        target = [180, 200]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        assert result_arr.mean() > 80, "Тёмное лицо должно стать ярче"
        assert before == 80.0, f"before должен быть 80.0, а не {before}"
        assert after > 80.0, f"after должен быть > 80.0, а не {after}"
        assert factor > 1.0, f"factor должен быть > 1.0 для тёмного лица, а не {factor}"

    def test_bright_face_gets_darkened(self):
        """Слишком яркое лицо (среднее 240) корректируется вниз."""
        gray = Image.new("L", (200, 200), 240)
        mask = Image.new("L", (200, 200), 255)
        target = [180, 200]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        assert result_arr.mean() < 240, "Яркое лицо должно стать темнее"
        assert factor < 1.0, f"factor должен быть < 1.0 для яркого лица"

    def test_correct_face_unchanged(self):
        """Лицо в целевом диапазоне не корректируется."""
        gray = Image.new("L", (200, 200), 190)
        mask = Image.new("L", (200, 200), 255)
        target = [180, 200]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        # Должно быть почти неизменным
        assert abs(result_arr.mean() - 190) < 3, \
            f"Лицо в диапазоне не должно корректироваться: {result_arr.mean():.0f}"
        assert factor == 1.0, f"factor должен быть 1.0 без коррекции"

    def test_empty_mask_returns_original(self):
        """Пустая маска — изображение не меняется."""
        gray = Image.new("L", (200, 200), 100)
        mask = Image.new("L", (200, 200), 0)  # пустая
        target = [180, 200]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        assert np.array(result).mean() == 100, "Пустая маска — без коррекции"
        assert before == 0.0, "before = 0.0 при пустой маске"
        assert factor == 1.0, "factor = 1.0 при пустой маске"
```

**Файл**: `tests/test_pipeline.py`

Обновить под новый API — существующие тесты `process()` продолжат работать (обратная совместимость). Добавить тесты для нового API:

```python
class TestPipelineStepsAPI:
    """Тесты нового API: process_steps, process_preview, process_export."""

    def test_process_steps_returns_pipeline_result(self, tmp_path):
        """process_steps() возвращает PipelineResult без сохранения файлов."""
        from retouch.processing.pipeline import process_steps, PipelineResult
        from retouch.config import DEFAULTS

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser", config=DEFAULTS)

        assert isinstance(result, PipelineResult)
        assert result.img_final is not None
        assert result.img_chromakey is not None
        assert result.width == 512
        assert result.height == 512
        assert result.glow_size > 0
        assert 0.0 <= result.face_brightness_before <= 255.0

    def test_process_preview_returns_small_result(self, tmp_path):
        """process_preview() уменьшает изображение до max_size."""
        from retouch.processing.pipeline import process_preview, PipelineResult
        from retouch.config import DEFAULTS

        input_path = self._save_chromakey_png(tmp_path, width=2048, height=2048)
        result = process_preview(input_path, machine_type="laser",
                                  config=DEFAULTS, max_size=768)

        assert isinstance(result, PipelineResult)
        assert result.width <= 768
        assert result.height <= 768

    def test_process_export_saves_files(self, tmp_path):
        """process_export() сохраняет TIFF + PNG и освобождает промежуточные."""
        from retouch.processing.pipeline import process_export, PipelineResult
        from retouch.config import DEFAULTS
        import os

        input_path = self._save_chromakey_png(tmp_path)
        output_tiff = str(tmp_path / "output.tiff")

        result = process_export(input_path, output_tiff,
                                 machine_type="laser", config=DEFAULTS)

        assert isinstance(result, PipelineResult)
        assert os.path.isfile(output_tiff), "TIFF не создан"
        assert result.img_final is not None
        assert result.img_chromakey is None  # Освобождено

    def test_release_intermediates_keeps_final(self, tmp_path):
        """release_intermediates() освобождает всё кроме img_final."""
        from retouch.processing.pipeline import process_steps, PipelineResult
        from retouch.config import DEFAULTS

        input_path = self._save_chromakey_png(tmp_path)
        result = process_steps(input_path, machine_type="laser", config=DEFAULTS)

        # До release — все промежуточные доступны
        assert result.img_chromakey is not None
        assert result.img_final is not None

        result.release_intermediates()

        # После release — промежуточные None, img_final доступен
        assert result.img_chromakey is None
        assert result.img_gray is None
        assert result.img_glow is None
        assert result.img_leveled is None
        assert result.img_face_corrected is None
        assert result.img_final is not None  # Важно!
        assert result.arch_mask is None
        assert result.subject_mask is None
```

---

## Задача 13: DEFAULTS — добавить face_region_top и highlight_start (A1)

**Файл**: `retouch/config.py`

Добавить два новых параметра в DEFAULTS для laser и impact:

```python
DEFAULTS = {
    "processing": {
        "blue_threshold": 30,
        "min_blue_ratio": 0.15,
        "min_resolution": 512,
        "result_min_black_ratio": 0.25,
        "fringe_radius": 3,
        "laser": {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
            "brightness": 1.18,
            "face_brightness_target": [230, 245],
            "face_region_top": 0.45,      # A1: доля высоты для зоны лица
            "highlight_start": 200,        # A1: порог затухания коррекции
        },
        "impact": {
            "glow_size_min": 10, "glow_size_max": 25,
            "glow_opacity_min": 60, "glow_opacity_max": 80,
            "brightness": 1.00,
            "face_brightness_target": [185, 210],
            "face_region_top": 0.45,      # A1
            "highlight_start": 200,        # A1
        },
    },
    "vignette": {
        "vertical_offset": 0.10,
        "vertical_diameter": 0.50,
        "blur_radius": 60,
        "headroom": 0.6,
        "horizontal_oversize": 0.2,
    },
}
```

**Файл**: `config.yaml`

Добавить параметры в обе секции:

```yaml
  laser:
    glow_size_min: 40
    glow_size_max: 80
    glow_opacity_min: 30
    glow_opacity_max: 40
    brightness: 1.18
    face_brightness_target: [230, 245]
    face_region_top: 0.45
    highlight_start: 200

  impact:
    glow_size_min: 10
    glow_size_max: 25
    glow_opacity_min: 60
    glow_opacity_max: 80
    brightness: 1.00
    face_brightness_target: [185, 210]
    face_region_top: 0.45
    highlight_start: 200
```

> **Примечание**: `shadow_noise` удаляется в Pre-0 (задача 4). Если Pre-0 ещё не выполнен — убрать `shadow_noise` при реализации этой задачи.

---

## Порядок выполнения

1. DEFAULTS — добавить `face_region_top` и `highlight_start` (задача 13) — **A1**
2. PipelineResult dataclass (задача 1) — **включая A15 docstring**
3. check_face_brightness() — новый возврат + face_region_top + исправленный псевдокод (задача 9) — **A4 + A1**
4. Обновление test_levels.py (задача 12)
5. process_steps() (задача 2) — скопировать логику из process(), убрать I/O — **A2 img.close()**
6. process_preview() с ресайзом (задача 3) — **A5 одно открытие изображения**
7. process_export() (задача 4)
8. process() → обёртка (задача 5)
9. Замена print() на logging + basicConfig (задача 6)
10. deep_merge + find_config_path() + load_config() с deepcopy (задача 7) — **find_config_path определена здесь же**
11. Pydantic-модель с conditional import (задача 8) — **A1 face_region_top + highlight_start в MachineConfig**
12. find_config_path() — **подтверждение экспорта** (задача 11.5, см. выше)
13. Публичные экспорты (задача 10)
14. Интеграционный CLI-тест (задача 11)
15. Обновление test_pipeline.py под новый API (задача 12)
16. `pytest tests/ -v` — все тесты проходят
17. `git tag phase0-done`

---

## Чеклист приёмки

### Функциональность

- [ ] `process_steps()` возвращает `PipelineResult` без сохранения файлов
- [ ] `process_steps()` вызывает `img.close()` после chromakey-шага — файловый дескриптор и память освобождаются (A2)
- [ ] `process_preview()` **реально уменьшает** изображение до max_size
- [ ] `process_preview()` открывает изображение **один раз** (A5) — нет двойного `Image.open()`
- [ ] `process_preview()` вызывает `img.close()` в обеих ветках (ресайз/без ресайза) — Windows-safe
- [ ] `process_preview()` закрывает дескриптор `tmp` ДО записи через PIL — Windows-safe
- [ ] `process_preview()` фиксирует glow на середине диапазона
- [ ] `process_export()` сохраняет TIFF + PNG и освобождает промежуточные
- [ ] `process()` — тонкая обёртка, CLI не сломан

### Код и качество

- [ ] Нет ни одного `print()` в pipeline.py и levels.py
- [ ] `logging.basicConfig()` вызывается в CLI — логгер не молчит
- [ ] `deep_merge` использует `copy.deepcopy` — DEFAULTS не мутируется
- [ ] `load_config()` выполняет deep_merge — частичный yaml дополняется DEFAULTS
- [ ] `validate_config()` использует Pydantic (если доступен), fallback на dict-проверки
- [ ] `check_face_brightness()` возвращает кортеж `(img, before, after, factor)`
- [ ] `check_face_brightness()` определяет `subject_mask_arr = np.array(subject_mask)` перед использованием (A4)
- [ ] `check_face_brightness()` обрезает зону замера через `face_region[cutoff:, :] = 0` (A4)
- [ ] `face_region_top` ограничивает зону замера яркости
- [ ] `highlight_start` вынесен из хардкода и передаётся через параметр
- [ ] `highlight_start` используется в `_curves_correction(arr, correction, highlight_start=200.0)`
- [ ] `apply_inner_glow` вызывается с правильными именами параметров
- [ ] `validate_result_black_ratio` вызывается на `img_final`, не на `Image.new`
- [ ] `release_intermediates()` имеет полный docstring с перечислением полей (A15)

### Конфигурация (A1)

- [ ] `face_region_top: 0.45` присутствует в DEFAULTS (laser и impact)
- [ ] `highlight_start: 200` присутствует в DEFAULTS (laser и impact)
- [ ] `face_region_top: 0.45` присутствует в config.yaml (laser и impact)
- [ ] `highlight_start: 200` присутствует в config.yaml (laser и impact)
- [ ] `face_region_top` в Pydantic `MachineConfig` с `Field(0.45, ge=0.2, le=0.8)`
- [ ] `highlight_start` в Pydantic `MachineConfig` с `Field(200, ge=100, le=250)`

### Тесты

- [ ] test_levels.py обновлён под новую сигнатуру `check_face_brightness()`
- [ ] test_pipeline.py обновлён — добавлены тесты для process_steps, process_preview, process_export
- [ ] `release_intermediates()` тестируется — `img_final` остаётся доступным
- [ ] `find_config_path()` определена в задаче 7 как часть `retouch/config.py` — единая точка поиска для CLI и backend
- [ ] `load_config()` использует `find_config_path()` — нет дублирования логики поиска
- [ ] Интеграционный CLI-тест проходит
- [ ] `pytest tests/ -v` — все тесты проходят

### Ресурсы

- [ ] RAM: PipelineResult с intermediates ~100 МБ при 2048×2048 (пик 150 МБ с numpy-массивами) (A19)

### Версия и GIMP

- [ ] Версия проекта: 3.0.0-dev (установлена в Pre-0)
- [ ] GIMP-пайплайн **сохранён** — команда `retouch gimp` работает с пометкой experimental
- [ ] Git-тег `phase0-done` создан
