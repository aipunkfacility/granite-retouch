# План рефакторинга granite-retouch

> Источник: аудит Claude Code + аудит v2 (критика этапов) + анализ кодовой базы + новые фичи
> Дата: 2026-05-08 (v4 — трёхуровневая детекция лица)
> Приоритет: P0 (критические баги) → P1 (архитектура) → P2 (улучшения) → P3 (новые фичи)

---

## Схема этапов

```
Этап A [багфиксы] ─────────────────────────────┐
  (0.1–0.5, TDD)                                │
                                                 ▼
Этап B [архитектура ядра] ──────────────┬───────┤
  (PipelineContext, конфиг,             │       │
   Analytics dataclass)                 │       │
                                        ▼       ▼
Этап C [face pipeline] ──────   Этап D [инфраструктура]
  (детекция, маска,          (preview/export, backend,
   conftest)                   frontend drag)
       │                      │
       ▼                      ▼
Этап E [FaceOval UI] ───────────────────────────┐
  (оверлей + интеграция)                         │
                                                 ▼
Этап F [качество кода] ─────────────────────────┐
  (расщепление, мониторинг, BMP)                │
                                                 ▼
Этап G [финальные тесты] ───────────────────────┘
  (интеграционные, регрессия)
```

**Параллелизм:** C и D — параллельно. E — после обоих. F — после E. G — последним.

---

## ЭТАП A: Багфиксы пайплайна (2–3 дня) — TDD ✅

> Зависимость: нет (начальный этап)
> Подход: **строго TDD** — сначала тест, воспроизводящий баг, потом фикс

### A.1 Shadow noise на фоне вместо субъекта

**Баг:** `add_shadow_noise()` добавляет шум в чёрные пиксели **фона**. На камне — паразитные точки вокруг портрета.

**TDD-цикл:**
1. 🔴 RED: написать тест — изображение с тёмным фоном → после noise → фон остаётся 0, шум только в субъекте
2. 🟢 GREEN: исправить `add_shadow_noise()` — шум в `subject_dark = mask_bool & (arr < shadow_threshold)`
3. 🟡 REFACTOR: вынести `shadow_threshold` в конфиг

```python
# Было (баг):
bg_mask = ~mask_bool
black_bg = bg_mask & (arr < 5)

# Стало:
subject_dark = mask_bool & (arr < shadow_threshold)  # из конфига, например 30
```

**Файлы:** `retouch/processing/levels.py` → `add_shadow_noise()`

---

### A.2 Shadow floor — отдельный шаг, НЕ в curves

**Баг:** при затемнении тени уходят в 0 без восстановления.

**TDD-цикл:**
1. 🔴 RED: тест — тёмное изображение → correction=0.7 → нет пикселей < shadow_floor при impact, есть при laser
2. 🟢 GREEN: добавить шаг в `pipeline.py` — `np.maximum(arr, shadow_floor)` только для impact
3. 🟡 REFACTOR: вынести shadow_floor в machine config

```python
# В pipeline.py, после curves_correction:
if machine_type == "impact":
    arr = np.maximum(np.array(img_face_corrected), shadow_floor)
    img_face_corrected = Image.fromarray(arr.astype(np.uint8), "L")
```

**Почему НЕ в `_curves_correction()`:** это универсальная функция яркости, а floor — machine-specific логика. Протаскивать её в curves = нарушение SRP.

**Файлы:** `retouch/processing/pipeline.py`

---

### A.3 Порядок шагов — Unsharp ПОСЛЕ face_brightness

**Баг:** unsharp до face_brightness → резкость смазывается коррекцией.

**TDD-цикл:**
1. 🔴 RED: тест — тёмное изображение → pipeline → проверить что unsharp вызван после face_brightness (mock-проверка порядка вызовов)
2. 🟢 GREEN: переставить порядок в `process_steps()`
3. 🟡 REFACTOR: добавить `legacy_step_order` для rollback

**Фиксированный конвейер:**
```
glow → levels → face_brightness → unsharp → shadow_noise → vignette
```

**⚠️ Требует перекалибровки:** после переключения — заново откалибровать `face_brightness_target` в config.yaml на 5-10 реальных заказах.

**Rollback:** `legacy_step_order: true` в config.yaml — вернуть старый порядок без redeploy.

**Файлы:** `retouch/processing/pipeline.py`

---

### A.4 Hard clamp белой точки перед экспортом

**Баг:** после shadow_noise и vignette могут появиться пиксели > white_ceiling.

**TDD-цикл:**
1. 🔴 RED: тест — pipeline → нет пикселей > white_ceiling
2. 🟢 GREEN: `np.clip(arr, 0, white_ceiling)` перед экспортом
3. 🟡 REFACTOR: white_ceiling из machine config

**Файлы:** `retouch/processing/pipeline.py`

---

### A.5 Glow rename + настоящий inner glow

**Баг:** `apply_inner_glow()` делает outer glow.

**TDD-цикл:**
1. 🔴 RED: тест — маска-круг → inner glow = свечение внутрь (ярче у края, затухает к центру), outer = наружу
2. 🟢 GREEN: переименовать текущий → `apply_outer_glow()`, написать `apply_inner_glow()` через shrink→edge→blur→composite
3. 🟡 REFACTOR: конфиг `glow_style: inner | outer`

```python
def apply_inner_glow(img_gray, subject_mask, glow_size=20, glow_opacity=80, glow_color=255):
    from scipy.ndimage import binary_erosion

    mask_arr = np.array(subject_mask) > 128
    shrunk = binary_erosion(mask_arr, iterations=glow_size // 2)
    edge = mask_arr & ~shrunk  # только внутренний край

    edge_img = Image.fromarray((edge * 255).astype(np.uint8), "L")
    edge_blurred = edge_img.filter(ImageFilter.GaussianBlur(glow_size // 2))

    glow_layer = Image.new("L", img_gray.size, glow_color)
    result = Image.composite(glow_layer, img_gray, edge_blurred)

    if glow_opacity < 100:
        result = Image.blend(img_gray, result, glow_opacity / 100.0)

    return result
```

**Файлы:** `retouch/processing/glow.py`

---

### Чеклист этапа A (до перехода к B)

- [ ] Все 5 багфиксов: тест-первым (RED→GREEN→REFACTOR)
- [ ] `face_brightness_target` перекалиброван на реальных заказах
- [ ] `legacy_step_order` работает как rollback
- [ ] `pytest tests/ -m p0` — все проходят

---

## ЭТАП B: Архитектура ядра (2 дня) — TDD 🟡

> Зависимость: после A
> Подход: частичный TDD — тесты на контракт, не на внутренности

### B.1 PipelineContext — внутренняя упаковка

**Проблема:** параметры пробрасываются через 5-6 функций.

**Подход:** `PipelineContext` dataclass — **только внутри `pipeline.py`**. Публичный API функций НЕ меняется.

```python
@dataclass
class PipelineContext:
    """Внутренний контекст — упаковка для pipeline.py.
    НЕ передаётся в функции обработки — они сохраняют текущие сигнатуры."""
    img_gray: Image.Image
    subject_mask: np.ndarray | None = None
    face_mask: Image.Image | None = None
    hair_mask: Image.Image | None = None
    analytics: dict | None = None
    machine_type: str = "laser_standard"
    config: dict = field(default_factory=dict)
    stone_type: str = "granite"
    stone_heterogeneity: float = 2.0
    step_mm: float = 0.300
    face_brightness_before: float = 0.0
    face_brightness_after: float = 0.0
    correction_factor: float = 1.0
```

**Тест:** pipeline с PipelineContext даёт тот же результат что без него (регрессия).

**Файлы:** `retouch/processing/pipeline.py`

---

### B.2 Миграция конфигурации

**Трёхуровневая система параметров:**

| Уровень | Источник | Пример | Приоритет |
|---|---|---|---|
| 1 (базовый) | `config.yaml` | `stone.type: granite` | низший |
| 2 (заказ) | `order.json` | `"stone_type": "gabbro"` | средний |
| 3 (сессия) | UI params | `stone_type: "marble"` | высший |

```yaml
# config.yaml — новые секции:
machine:
  step_mm: 0.300
stone:
  type: granite
  heterogeneity: null  # null = auto по stone_type → STONE_PROFILES
```

**Тест:** параметр из UI перекрывает order.json, order.json перекрывает config.yaml.

**Файлы:** `retouch/processing/config.py`, `retouch_ui/backend/routers/process.py`

---

### B.3 Analytics dataclass

**Подход:** dataclass с теми же именами полей что ключи dict — тесты не ломаются.

```python
@dataclass
class ImageAnalytics:
    median: float; mean: float; p10: float; p25: float
    p75: float; p90: float; tonal_range: float; clipping_pct: float
    bg_median: float; bg_std: float; separation: float
    input_class: str

    @classmethod
    def from_dict(cls, d: dict) -> "ImageAnalytics":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)
```

**Тест:** `from_dict(старый_dict).to_dict() == старый_dict` (круговой обход).

**Файлы:** `retouch/processing/analysis.py`

---

### Чеклист этапа B

- [ ] PipelineContext создан, pipeline с ним = pipeline без него
- [ ] Конфиг: трёхуровневое переопределение работает
- [ ] `ImageAnalytics.from_dict()` / `.to_dict()` — обратная совместимость
- [ ] Все существующие тесты проходят

---

## ЭТАП C: Face pipeline (2–3 дня) — TDD ✅

> Зависимость: после B
> Подход: TDD — чистые функции, детерминированный вывод

### C.1 Улучшенная эвристика — профиль ширины маски

**Почему НЕ mediapipe сейчас:**

Для текущих шагов пайплайна разница между эвристикой и mediapipe — ±3% в коррекции яркости. На камне незаметно. mediapipe тянет 130 MB зависимостей (opencv-contrib 79 MB, matplotlib 9 MB) + требует libGLESv2 на сервере + не работает на Linux ARM64 + ограничен Python 3.12. Это неоправданно для текущей пользы.

**Когда mediapipe станет нужен:** когда фичи #2 (unsharp раздельно), #3 (hair clarity), #6 (inpainting) будут реализованы — вот тогда точная маска лица будет критична. До этого момента — улучшенная эвристика + ручной овал.

**Алгоритм — профиль ширины маски:**

У нас уже есть subject_mask. Профиль ширины маски по вертикали выдаёт структуру портрета:

```
Ширина маски
    ▲
    │     ╱╲          ← волосы (узко → расширяется)
    │    ╱  ╲
    │   ╱    ╲        ← лоб → лицо (максимальная ширина = скулы)
    │  ╱      ╲
    │ ╱        ╲      ← шея (сужение)
    │╱          ╲
    │            ╲╱    ← плечи (шире)
    └──────────────→ Высота
```

Первый локальный максимум ширины сверху = уровень скул = зона лица.

**TDD-цикл:**
1. 🔴 RED: тест — стандартный портрет → face_region найден (верхняя граница лица выше скул, нижняя = скулы)
2. 🔴 RED: тест — портрет по пояс → face_region найден несмотря на плечи
3. 🔴 RED: тест — пустое изображение (нет маски) → fallback на верхние 45%
4. 🟢 GREEN: реализовать `_detect_face_by_width_profile()`
5. 🟡 REFACTOR: вынести в отдельную функцию, параметризовать

```python
# retouch/processing/face_region.py

def _detect_face_by_width_profile(subject_mask, img_height, img_width):
    """Найти зону лица по профилю ширины маски.

    Первый локальный максимум ширины сверху = уровень скул.
    Лицо = от макушки до уровня скул (с запасом вниз).
    Возвращает FaceOvalParams или None (если профиль нечитаем).
    """
    mask_arr = np.array(subject_mask) > 128
    widths = mask_arr.sum(axis=1)  # ширина по каждой строке

    # Скользящее среднее (сгладить шум маски)
    kernel_size = max(1, img_height // 50)  # адаптивный kernel
    kernel = np.ones(kernel_size) / kernel_size
    smooth = np.convolve(widths, kernel, mode='same')

    # Первый локальный максимум сверху = скулы
    face_row = None
    for i in range(kernel_size, len(smooth) - kernel_size):
        if smooth[i] > smooth[i-1] and smooth[i] >= smooth[i+1]:
            face_row = i  # строка максимальной ширины
            break

    if face_row is None:
        return None  # профиль нечитаем → fallback

    # Лицо ≈ от макушки до скул с запасом вниз
    # Высота лица ≈ ширина в точке скул (лицо ~овальное)
    face_width_px = smooth[face_row]
    face_height_px = int(face_width_px * 1.2)  # с запасом

    # Центр овала
    cx_norm = 0.5  # по горизонтали — центр
    cy_norm = (face_row - face_height_px // 2) / img_height
    rx_norm = (face_width_px / 2) / img_width
    ry_norm = (face_height_px / 2) / img_height

    return {
        "cx": cx_norm, "cy": cy_norm,
        "rx": rx_norm, "ry": ry_norm,
        "source": "heuristic"
    }


def detect_face_oval(img_gray, subject_mask=None) -> dict:
    """Детекция зоны лица → FaceOvalParams.

    Трёхуровневая стратегия:
      1. Улучшенная эвристика (профиль ширины маски) — покрывает 85-90%
      2. Ручной овал (FaceOvalOverlay) — покрывает оставшиеся 10-15%
      3. mediapipe FaceLandmarker — в будущем, когда фичи #2, #3, #6 будут готовы

    Returns: {cx, cy, rx, ry, source: "heuristic"} или legacy fallback
    """
    if subject_mask is not None:
        result = _detect_face_by_width_profile(
            subject_mask, img_gray.height, img_gray.width)
        if result is not None:
            return result

    # Fallback: текущая эвристика (верхние 45%)
    return {
        "cx": 0.5, "cy": 0.25,
        "rx": 0.25, "ry": 0.20,
        "source": "heuristic_legacy"
    }
```

**Сравнение подходов к детекции лица:**

| Подход | Покрытие | Зависимости | Латентность | Когда использовать |
|---|---|---|---|---|
| Улучшенная эвристика | 85-90% | 0 MB | ~1 ms | **Сейчас** — достаточно для текущих шагов |
| Ручной овал (UI) | 100% | 0 MB | 0 ms | **Сейчас** — для нестандартных случаев |
| mediapipe FaceLandmarker | 95-98% | 130 MB + libGLESv2 | ~14 ms | **Позже** — когда фичи #2, #3, #6 будут готовы |

**Файлы:** новый `retouch/processing/face_region.py` (детекция + маска в одном модуле)

---

### C.2 Маска лица и волос из овала

**TDD-цикл:**
1. 🔴 RED: тест — овал (0.5, 0.25, 0.15, 0.20) → маска = эллипс ∩ subject_mask
2. 🔴 RED: тест — hair_mask: выше овала + gap_ratio
3. 🔴 RED: тест — face_oval=None → legacy fallback (верхние 45%)
4. 🟢 GREEN: `generate_face_mask()`, `generate_hair_mask()`
5. 🟡 REFACTOR: параметризовать gap_ratio

```python
def generate_face_mask(width, height, face_oval, subject_mask):
    """Создать маску лица из овала + маски субъекта."""
    if face_oval is None:
        return _heuristic_face_mask(width, height, subject_mask, top_ratio=0.45)

    cx = int(face_oval['cx'] * width)
    cy = int(face_oval['cy'] * height)
    rx = int(face_oval['rx'] * width)
    ry = int(face_oval['ry'] * height)

    oval = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(oval)
    draw.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], fill=255)

    if subject_mask is not None:
        oval = ImageChops.multiply(oval, subject_mask)
    return oval


def generate_hair_mask(face_mask, subject_mask, gap_ratio=0.05):
    """Маска волос = субъект выше овала лица с зазором.
    gap_ratio — доля высоты изображения (масштабонезависимо)."""
    gap_px = int(face_mask.height * gap_ratio)
    ...
```

**Файлы:** `retouch/processing/face_region.py` (детекция + маска в одном модуле)

---

### C.3 Интеграция в пайплайн

**TDD-цикл:**
1. 🔴 RED: тест — pipeline с face_oval → face_mask используется в check_face_brightness
2. 🟢 GREEN: pipeline.py создаёт face_mask, передаёт дальше
3. 🟡 REFACTOR: check_face_brightness принимает face_mask вместо face_region_top

**Файлы:** `retouch/processing/pipeline.py`, `retouch/processing/levels.py`

---

### C.4 Обновление conftest.py

```python
@pytest.fixture
def sample_face_oval():
    return {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20, "source": "auto"}

@pytest.fixture
def sample_pipeline_context(img_gray_512, subject_mask_512):
    return PipelineContext(img_gray=img_gray_512, subject_mask=subject_mask_512,
                           machine_type="impact")

@pytest.fixture
def sample_analytics():
    return ImageAnalytics(median=130.0, mean=125.0, p10=45.0, p25=80.0,
                           p75=180.0, p90=210.0, tonal_range=165.0,
                           clipping_pct=0.5, bg_median=10.0, bg_std=5.0,
                           separation=120.0, input_class="medium")
```

**Файлы:** `tests/conftest.py`

---

### Чеклист этапа C

- [ ] Улучшенная эвристика: стандартный портрет → face_region найден через профиль ширины
- [ ] Улучшенная эвристика: нестандартный → fallback на legacy (верхние 45%)
- [ ] `generate_face_mask()`: овал ∩ subject_mask
- [ ] `generate_hair_mask()`: выше овала + gap_ratio
- [ ] Pipeline использует face_mask вместо face_region_top
- [ ] conftest.py обновлён
- [ ] 0 новых зависимостей (никакого mediapipe на этом этапе)

---

## ЭТАП D: Инфраструктура (2–3 дня) — TDD 🟡

> Зависимость: после B (нужен PipelineContext для кэша)
> Параллелен с C
> Подход: TDD на логику (валидация, хэш, TTL), без TDD на UI

### D.1 Preview-Export consistency — glow

Убрать рандомизацию glow → deterministic через analytics. Если analytics нет → midpoint.

**Тест:** pipeline с одними параметрами → preview glow == export glow.

**Файлы:** `retouch/processing/glow.py`, `retouch/processing/pipeline.py`

---

### D.2 Preview — размер для широких кадров

`max_size` применять если обе стороны > max_size. Минимальная высота ≥ 200.

```python
img.thumbnail((max_size, max_size))
if img.height < 200:
    ratio = 200 / img.height
    new_w = min(int(img.width * ratio), max_size * 3)
    img = img_original.copy()
    img.thumbnail((new_w, max_size))
```

**Тест:** 4000×500 → height ≥ 200, width ≤ max_size * 3.

**Файлы:** `retouch/processing/pipeline.py`

---

### D.3 Preview — оптимизация payload

Два режима: `full_steps: true` (первый запрос — все шаги), `full_steps: false` (только selected + final).

**Файлы:** `retouch_ui/backend/routers/process.py`, `schemas.py`, `use-preview.ts`

---

### D.4 Валидация параметров (Pydantic)

```python
class PreviewParams(BaseModel):
    brightness: float | None = Field(None, ge=0.5, le=2.0)
    glow_size: int | None = Field(None, ge=5, le=100)
    glow_opacity: int | None = Field(None, ge=0, le=100)
    face_oval: FaceOvalParams | None = None
    stone_type: str | None = Field(None, pattern="^(granite|marble|gabbro|basalt)$")
    step_mm: float | None = Field(None, ge=0.10, le=0.50)
```

**Тест:** `brightness=999` → 422 Validation Error.

**Файлы:** `retouch_ui/backend/schemas.py`

---

### D.5 TTL cleanup + reference counting

**Тест:** файл с ref_count > 0 не удаляется при TTL cleanup.

**Файлы:** `retouch_ui/backend/routers/process.py`

---

### D.6 Кэш preview

**TDD-цикл:**
1. 🔴 RED: `_stable_serialize({a: 1.0}) == _stable_serialize({a: 1.0000})` — один хэш
2. 🔴 RED: кэш хранит base64, не PIL objects
3. 🟢 GREEN: реализовать `_stable_serialize()`, `_cache_key()`, base64-only кэш

**Файлы:** `retouch_ui/backend/routers/process.py`

---

### D.7 Предупреждение при перезаписи экспорта

НЕ timestamp в имени (ломает CLI). Предупреждение + `--overwrite` флаг.

**Файлы:** `retouch/processing/pipeline.py`, CLI

---

### D.8 Frontend — drag interactions

- **D.8.1** Pointer events на `window` (VignetteOverlay + FaceOvalOverlay)
- **D.8.2** Bounds checking в `computeParamsFromDrag`
- **D.8.3** Race conditions в `usePreview` (version counter)

**Без TDD** — ручное тестирование + визуальная проверка.

**Файлы:** `vignette-overlay.tsx`, `face-oval-overlay.tsx`, `vignette-geometry.ts`, `use-preview.ts`

---

### Чеклист этапа D

- [ ] Preview glow == export glow
- [ ] Широкий кадр: height ≥ 200
- [ ] `full_steps` режим работает
- [ ] Pydantic валидация отбрасывает невалидные параметры
- [ ] TTL не удаляет активные файлы
- [ ] Кэш: стабильный хэш, base64-only
- [ ] Экспорт: предупреждение при перезаписи
- [ ] Drag: pointer events, bounds, race conditions

---

## ЭТАП E: FaceOval UI + интеграция (2–3 дня) — TDD ❌

> Зависимость: после C (face pipeline) + D (frontend drag fixes)
> Подход: без TDD — UI-компонент, ручное тестирование

### E.1 FaceOvalOverlay — интерактивный овал (ручная корректировка)

По аналогии с VignetteOverlay:
- SVG-эллипс с 4 drag handles
- Параметры: `cx`, `cy`, `rx`, `ry` (0-1)
- Появляется автоматически с координатами из улучшенной эвристики — пользователь видит результат и может скорректировать
- `source: "heuristic"` → `"manual"` при первом drag
- Для 85-90% портретов овал будет на месте — пользователь не трогает
- Для 10-15% нестандартных — пользователь перетаскивает

**Файлы:**
- Новый: `face-oval-overlay.tsx`
- Новый: `face-oval-geometry.ts`
- Изменить: `App.tsx` — добавить overlay
- Изменить: `process.py` — принять face_oval

---

### E.2 Сквозная интеграция

UI oval → API → pipeline → face_mask → check_face_brightness → результат

**Ручное тестирование:**
1. Загрузить портрет → эвристика находит лицо через профиль ширины → овал на месте (85-90% случаев)
2. Перетащить овал → preview обновляется (10-15% случаев — нестандартные портреты)
3. Export → результат с маской лица (эвристической или ручной)

---

### Чеклист этапа E

- [ ] FaceOvalOverlay рендерится поверх изображения
- [ ] Drag работает (window pointer events из D.8)
- [ ] Эвристика → овал на месте → можно скорректировать
- [ ] Не удалось определить → legacy fallback → можно перетащить
- [ ] Preview → export: маска лица совпадает
- [ ] 0 новых зависимостей (ручной овал — чистый UI)

---

## ЭТАП F: Качество кода (2–3 дня) — TDD 🟡

> Зависимость: после E
> Подход: TDD на новые модули, без TDD на рефакторинг

### F.1 Расщепление levels.py

Переезд функций в отдельные модули + backward-compatible re-exports:

| Новый модуль | Функции |
|---|---|
| `levels.py` | `apply_levels()`, `_adaptive_levels_factor()` |
| `unsharp.py` | `apply_unsharp_mask()`, `_adaptive_unsharp_percent()` |
| `face_correction.py` | `check_face_brightness()`, `_curves_correction()` |
| `shadow_noise.py` | `add_shadow_noise()` |
| `face_region.py` | `generate_face_mask()`, `generate_hair_mask()` |

**Без TDD** — поведение не меняется, существующие тесты = safety net.

---

### F.2 Мониторинг качества

Метрики в PipelineResult: `clipped_pixels_pct`, `shadow_crush_pct`, `tonal_range_output`, `correction_aggression`, `warnings`.

**TDD:** тест — тёмное изображение с агрессивной коррекцией → warnings не пустой.

**Файлы:** `retouch/processing/pipeline.py`

---

### F.3 Валидация выходного BMP

Post-save проверка: mode == 'L' и size совпадает.

**TDD:** save → reopen → assert.

**Файлы:** `retouch/processing/export.py`

---

### Чеклист этапа F

- [ ] levels.py расщеплён, re-exports работают
- [ ] Метрики качества собираются, warnings формируются
- [ ] BMP post-save валидация работает
- [ ] Все существующие тесты проходят

---

## ЭТАП G: Финальные тесты (1–2 дня) — TDD ✅

> Зависимость: после F (последний этап)
> Подход: TDD — пишем недостающие тесты

### G.1 Регрессионные тесты (P0)

| Модуль | Тест |
|---|---|
| `export.py` | Floyd-Steinberg: grayscale 128 → 50% white, 50% black |
| `export.py` | BMP 8-bit roundtrip: save → reopen → same pixels |
| `export.py` | BMP 1-bit: save → reopen → mode='1' |
| `levels.py` | Shadow noise: шум в субъекте, не на фоне |
| `pipeline.py` | Shadow floor: impact → нет < floor, laser → есть |
| `pipeline.py` | Порядок шагов: unsharp после face_brightness |
| `pipeline.py` | White clamp: нет пикселей > white_ceiling |

### G.2 Функциональные тесты (P1)

| Модуль | Тест |
|---|---|
| `glow.py` | Inner glow: shrink→edge→blur = свечение внутрь |
| `glow.py` | Outer glow: свечение наружу |
| `analysis.py` | `_classify_input`: граничные значения 120, 180, 220 |
| `analysis.py` | `ImageAnalytics.from_dict()` → `.to_dict()` == исходный dict |
| `pipeline.py` | Wide image 4000×500 → height ≥ 200, width ≤ max_size*3 |
| `face_region.py` | `generate_face_mask`: овал ∩ subject_mask |
| `face_region.py` | `generate_hair_mask`: выше овала + gap_ratio |
| `face_region.py` | Профиль ширины маски → face_region найден |
| `face_region.py` | Нечитаемый профиль → fallback legacy (45%) |
| `face_region.py` | Портрет по пояс → плечи не путаются с лицом |
| `cache` | `_stable_serialize`: float 1.0 == 1.0000 → один хэш |
| `cache` | Кэш хранит base64, не PIL |
| `schemas.py` | `brightness=999` → 422 |
| `config.py` | UI > order.json > config.yaml > defaults |

### G.3 Интеграционный тест

Сквозной: загрузка → эвристика (профиль ширины) → овал на UI → корректировка (если нужно) → preview → export → BMP валидация.

---

### Чеклист этапа G

- [ ] Все P0 тесты проходят
- [ ] Все P1 тесты проходят
- [ ] Интеграционный тест проходит
- [ ] `pytest tests/ --tb=short` — 0 failed

---

## Сводка по TDD

| Этап | TDD | Деталь |
|---|---|---|
| **A** Багфиксы | ✅ Строго | Тест воспроизводит баг → фикс → тест проходит |
| **B** Архитектура ядра | 🟡 Частично | Тест на контракт, не на внутренности |
| **C** Face pipeline | ✅ Строго | Чистые функции (эвристика + маска), 0 зависимостей |
| **D** Инфраструктура | 🟡 Частично | TDD на логику, без TDD на UI |
| **E** FaceOval UI | ❌ Нет | Визуал/взаимодействие — ручное тестирование |
| **F** Качество кода | 🟡 Частично | TDD на новые модули, без TDD на рефакторинг |
| **G** Тесты | ✅ Строго | Пишем недостающие тесты — это и есть TDD |

---

## Таймлайн

```
Неделя 1 (5 дней):
  Пн-Ср: Этап A (багфиксы, TDD)
  Чт-Пт: Этап B (архитектура ядра)

Неделя 2 (5 дней):
  Пн-Чт: Этап C + D — ПАРАЛЛЕЛЬНО
    C: face pipeline (1 чел)
    D: инфраструктура (1 чел)
  Пт: синхронизация C+D

Неделя 3 (5 дней):
  Пн-Ср: Этап E (FaceOval UI + интеграция)
  Чт-Пт: Этап F (качество кода)

Неделя 4 (2 дня):
  Пн-Вт: Этап G (финальные тесты)

Итого: 13-16 дней (3 недели)
```

Если один разработчик — последовательно: A → B → C → D → E → F → G = ~16 дней.
Если два — C и D параллельно на неделе 2 = ~13 дней.

> ⏱️ Этап C стал на 1 день короче — нет настройки mediapipe (130 MB зависимостей, libGLESv2, separate model file). Улучшенная эвристика — 0 зависимостей, ~1ms.

---

## Дорожная карта: когда добавлять mediapipe

**Сейчас (этапы A–G):** улучшенная эвристика + ручной овал. Покрывает 90-95% случаев. 0 зависимостей.

**Позже (когда фичи #2, #3, #6 будут готовы):** добавить mediapipe FaceLandmarker как третий уровень детекции. Архитектура уже поддерживает это — `detect_face_oval()` просто попробует mediapipe первым, а эвристику как fallback.

```python
# Будущий код (когда mediapipe будет добавлен):
def detect_face_oval(img_gray, subject_mask=None) -> dict:
    # Уровень 1: mediapipe (самый точный, ~14ms)
    result = _detect_face_mediapipe(img_gray)
    if result is not None:
        return result  # source: "auto"

    # Уровень 2: улучшенная эвристика (~1ms)
    if subject_mask is not None:
        result = _detect_face_by_width_profile(subject_mask, ...)
        if result is not None:
            return result  # source: "heuristic"

    # Уровень 3: legacy fallback
    return {"cx": 0.5, "cy": 0.25, "rx": 0.25, "ry": 0.20, "source": "heuristic_legacy"}
```

**Триггер для добавления mediapipe:** реализация фичи #2 (unsharp раздельно) или #6 (inpainting) — когда точная маска лица станет критична для результата на камне.

**Затраты на добавление mediapipe:** ~1 день (pip install + model download + интеграция в detect_face_oval + тесты).

---

## Связь с new-features-pipeline.md

| Фича | Зависит от | Почему |
|---|---|---|
| #2 Unsharp раздельно | Этап C (face mask) + **mediapipe** | Улучшенной эвристики достаточно для разделения лицо/одежда; mediapipe повысит точность |
| #3 Hair clarity | Этап C (hair mask) + **mediapipe** | Маска волос выше овала; mediapipe даст точную границу лицо/волосы |
| #5 Белая аура | Этап A.5 (glow rename) | Outer glow уже есть — переименовать + inner |
| #6 Inpainting пересветов | Этап C (face mask) + **mediapipe** | Маска лица ограничивает зону; mediapipe даст точную маску для inpainting |
| #7 Heterogeneity | Этап B.1 (PipelineContext) | Параметр в контексте |
| #8 Симуляция | Этап F.2 (мониторинг) | Использует метрики качества |
| #9 Stone boost | Этап B.1 (PipelineContext) | Переиспользует heterogeneity |
| #10 BMP resolution | Этап B.2 (конфиг) | machine.step_mm из конфига |
| #11 Stone type | Этап B.2 (конфиг) | stone_type + heterogeneity |
| #12 Stochastic dither | Этап A.4 (clamp) + B.1 | Нужен clamp перед дизерингом |
