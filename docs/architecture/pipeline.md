# Пайплайн обработки

Полный конвейер обработки портрета: от PNG с синим хромакеем до BMP с чёрным фоном.

Запуск: `python -m retouch process -i ai.png -o final.bmp -m laser_standard`

---

## Шаги пайплайна

### 1. Валидация входного изображения

**Модуль:** `retouch/validation/image.py`

Проверки:
- Файл существует и открывается Pillow
- Формат: PNG, JPEG, TIFF
- Разрешение >= `min_resolution` (default: 512px)
- Разрешение <= `max_resolution` (default: 8192px) — защита от OOM
- Синий хромакей: >= `min_blue_ratio` (default: 15%) синих пикселей

Ошибка → `ValidationError` + exit 1.

### 2. Загрузка и конвертация в RGBA

```python
img = Image.open(input_path).convert("RGBA")
```

### 3. Удаление синего хромакея + fringe removal + градиентная маска

**Модуль:** `retouch/processing/detection/chromakey.py`

- **Градиентная маска**: вместо бинарного порога вычисляет «степень синевы» через soft-step. Альфа-канал = 1 − blue_strength. Плавный переход на контуре следует за реальным градиентом синевы, а не за пиксельной решёткой
- Fringe removal: расширяет бинарную маску на `fringe_radius` пикселей и плавно гасит синий канал в переходной зоне (использует бинарный порог отдельно от градиентной альфы)
- `_make_smooth_mask` (DEPRECATED): ранее использовался OpenCV contour tracing для антиалиасинга. Заменён на градиентную маску, которая работает без cv2
- Параметр `contour_smooth_epsilon` DEPRECATED — игнорируется градиентной маской
- Софт-маска субъекта: `GaussianBlur(gradient_mask, sigma=mask_soft_sigma)` для плавных краёв в последующих шагах (glow, face_correction)
- Выход: изображение RGBA (без фона, градиентный альфа-канал) + маска субъекта L (255 = субъект, промежуточные значения на контуре)

### 4. Конвертация в Grayscale

```python
img_gray = img.convert("L")
```

Изображение становится одноканальным. Все дальнейшие шаги работают в режиме L.

### 4a. Детекция зоны лица (C.1)

**Модуль:** `retouch/processing/detection/face_region.py`

Трёхуровневая стратегия определения зоны лица:

1. **Профиль ширины маски** (~85-90% портретов) — анализирует ширину маски субъекта по вертикали. Первый локальный максимум ширины сверху = уровень скул → зона лица. Быстро (~1ms), 0 зависимостей. **Примечание:** на типичных AI-ретушах с хромакеем маска часто имеет гладкий профиль (голова+плечи = единая масса), поэтому локальные максимумы могут не соответствовать анатомии лица. В таких случаях автоопределение ставит овал «где-то вверху» — оператор всегда корректирует вручную.
2. **Ручной овал** (FaceOvalOverlay в UI) — пользователь корректирует овал для нестандартных портретов. Параметры: `cx`, `cy`, `rx`, `ry` (0–1, нормализованные). `source: "manual"` при перетаскивании
3. **mediapipe FaceLandmarker** (будущее) — будет добавлен, когда фичи #2, #3, #6 потребуют точную маску лица. Тянет 130 MB зависимостей

Функция `detect_face_oval(img_gray, subject_mask=None)` возвращает `FaceOvalParams` dict: `{cx, cy, rx, ry, source}`.

#### Pin Face Oval (v6.0)

Механизм фиксации овала лица в Web UI:

- **Pin OFF** (по умолчанию) — овал обновляется из автодетекции при каждом preview
- **Pin ON** — овал зафиксирован, не обновляется из автодетекции
- **Авто-Pin** — при ручном перемещении овала (`source: "manual"`) Pin автоматически включается
- **Unpin** — кнопка-пин переключает состояние, разрешая автообновление

Логика в `App.tsx`:

```ts
useEffect(() => {
  if (previewResult?.diagnostics?.face_oval && !faceOvalOverlayEnabled && !faceOvalPinned) {
    setFaceOval(previewResult.diagnostics.face_oval);
  }
}, [previewResult, faceOvalOverlayEnabled, faceOvalPinned]);
```

| Состояние | Что происходит при preview |
|-----------|---------------------------|
| Overlay OFF, Pin OFF | Овал обновляется из автодетекции |
| Overlay OFF, Pin ON | Овал НЕ обновляется, фиксируется |
| Overlay ON, любой Pin | Овал обновляется из ручного drag |

### 4b. Генерация маски лица и волос из овала (C.2)

**Модуль:** `retouch/processing/detection/face_region.py`

- `generate_face_mask(width, height, face_oval, subject_mask)` — создаёт эллипс по овалу ∩ subject_mask. Если `face_oval` не задан — legacy fallback (верхние 45%)
- `generate_hair_mask(face_mask, subject_mask, gap_ratio=0.05)` — маска волос = субъект выше овала лица с зазором `gap_ratio` (доля высоты изображения)

Маска лица точнее, чем топологический `face_region_top` — овал ограничивает замер яркости зоной лица, исключая лоб/волосы/шею.

### 4c. Преданализ (analytics)

**Модуль:** `retouch/processing/analysis/analysis.py`

После конвертации в grayscale pipeline измеряет 13 метрик входного изображения **внутри маски лица** (если face_mask доступен, иначе — внутри маски субъекта). Метрики по лицу точнее — чёрная одежда не тянет медиану вниз (FIX-ORD-007).

| Метрика | Описание |
|---------|----------|
| `median_brightness` | Медианная яркость лица |
| `mean_brightness` | Средняя яркость лица |
| `p10_brightness` / `p90_brightness` | Глубокие тени / блики (перцентили) |
| `tonal_range` | Тональный диапазон (p90 - p10) |
| `highlight_clipping_pct` | % пикселей ≥250 (пересвет) |
| `shadow_clipping_pct` | % пикселей ≤5 (провалы) |
| `bg_median_brightness` | Медианная яркость фона (~0 после хромакея) |
| `subject_separation` | |face_median - bg_median| |
| `input_class` | Классификация: dark / medium / bright / overbright |

Метрики возвращаются в виде `ImageAnalytics` dataclass с методами `from_dict()`/`to_dict()` для обратной совместимости. Результат передаётся во все последующие шаги (Glow, Levels, Unsharp). Если numpy недоступен — используется legacy mode с фиксированными параметрами из конфига.

### 4d. Зональное разделение (ZoneMasks)

**Модуль:** `retouch/processing/analysis/zones.py`

Изображение разбивается на дизъюнктные технические зоны для дифференцированной обработки:

| Зона | Описание | Порог |
|------|----------|-------|
| `face_skin` | Кожа лица (адаптивный порог по `median_brightness`) | `face_skin_threshold` (default: 100) |
| `face_dark` | Тёмные участки лица (брови, тени, борода) | ниже skin_threshold |
| `hair` | Волосы (субъект выше овала лица) | — |
| `clothes` | Одежда (субъект ниже овала лица) | — |
| `highlights` | Яркие зоны субъекта | `highlight_start` (default: 200) |
| `contour_inner` | Внутренний край для glow | из gradient/fallback morphological |
| `contour_outer` | Внешний край для антифринги | из gradient |
| `background` | Фон (вне маски субъекта) | — |

`build_zone_masks()` возвращает `ZoneMasks` dataclass. `resolve_zone_priority()` гарантирует дизъюнктность масок (каждый пиксель принадлежит только одной зоне). Приоритет: highlights > face_skin > face_dark > hair > clothes > contour_inner. `background` явно исключён из priority resolution — не получает тональных коррекций.

Дополнительные возможности:
- **Адаптивный порог кожи:** двухпроходной алгоритм — Pass 1: coarse_skin = face_pixels >= threshold, Pass 2: histogram_mode(coarse_skin) сглаживание → clamp(mode - delta, min, max)
- **Beard detection:** если face_dark > 40% лица и концентрируется в нижней трети овала — подозрение бороды, переклассификация face_dark → hair
- **Contour fallback:** если gradient-маска некачественная (>30% subject), автоматический fallback на morphological contour (dilate - erode)

### 5. Glow (inner | outer, детерминированный)

**Модуль:** `retouch/processing/correction/glow.py`

Параметры glow **детерминированы** (D.1): при наличии analytics — midpoint адаптивного диапазона через `_calculate_glow_params()`, без analytics — midpoint диапазона из конфига. Рандомизация полностью устранена для preview-export consistency.

Стиль glow задаётся параметром `glow_style` в конфиге:
- **`inner`** — свечение внутрь (настоящий inner glow через `apply_inner_glow_algorithm()`: shrink→edge→blur→brightness-weighted→composite). Ярче у внутреннего края субъекта, затухает к центру. С яркостным весом — свечение неравномерное: сильнее на тёмных участках контура (где rim light нужен для сепарации), слабее на светлых (где уже есть контраст). Это даёт естественный вид, а не равномерную «аппликацию» по всему силуэту
- **`outer`** — свечение наружу (классический glow, `apply_outer_glow()`). Инвертированная маска → blur → composite

Диспетчер `apply_glow()` выбирает реализацию по `glow_style`.

Параметры зависят от типа станка и аналитики:
- **Laser Standard:** glow 40–80px, opacity 30–40% (широкий, мягкий)
- **Laser 80W:** фиксированные параметры (15–25, 10–20) — мощный лазер сам создаёт контраст. Glow фиксируется на середине диапазона для обеспечения детерминированности (D.1).
- **Impact:** параметры зависят от `subject_separation` и `tonal_range` — при низкой сепарации glow усиливается

### 6. Face Brightness Correction (bounded delta + curves)

**Модуль:** `retouch/processing/correction/face_brightness.py`

> **Переименование**: ранее функция называлась `check_face_brightness()` в модуле `face_correction.py`. Начиная с v6.4 — `face_brightness_correction()` в `face_brightness.py`.

Двусторонняя bounded delta формула (рефакторинг v6.4):
- `target_pre_fb`: laser_standard=180, laser_80w=150, impact=160
- `delta = target_pre_fb - median_brightness`, ограничен `±max_delta`
- `factor = 1 + delta / median_brightness`, ограничен `[min_factor, max_factor]`
- Защита от клиппинга: если `p90 * factor > 250` → фактор снижается
- Без analytics — legacy mode (фиксированный `brightness_factor` из конфига)

Нелинейная (curves) коррекция:
- Тени корректируются полностью, света минимально
- Это поднимает лицо (тёмное) без пересвета воротника (светлого)
- Коррекция применяется только внутри `subject_mask`

Целевые диапазоны по типу станка:
- **Laser Standard:** 230–245, white_ceiling: 250, highlight_start: 210
- **Laser 80W:** 160–210, white_ceiling: 235, highlight_start: 195
- **Impact:** 170–215, white_ceiling: 245, highlight_start: 185

`highlight_start` вычисляется по формуле `white_ceiling - 40`, чтобы коррекция уровней плавно затухала только после достижения целевой яркости лица.

### 6a. Масочная защита

`face_brightness_correction()` и `apply_unsharp_mask()` принимают `subject_mask` и `face_skin_mask`. Пиксели вне маски (фон) остаются без изменений — предотвращает серую дымку на чёрном фоне и halo на границе субъект/фон. Это критично: после хромакея фон должен быть абсолютно чёрным (~0), и любая коррекция яркости или резкости за пределами маски субъекта создаёт видимые артефакты на готовой гравировке.

### 7. Unsharp Mask (адаптивный, с face_skin overshoot limit)

**Модуль:** `retouch/processing/correction/unsharp.py`

Unsharp mask теперь **ПОСЛЕ** face_brightness correction (A.3). Старый порядок доступен через `legacy_step_order: true` в config.yaml.

- `ImageFilter.UnsharpMask(radius=1.5, percent=<adaptive>, threshold=0)`
- Адаптивный percent зависит от analytics:
  - `overbright` → 80 (сниженный — пересвету резкость не нужна)
  - `tonal_range < 40` → 150 (усиленный — узкий диапазон требует чёткости)
  - Норма → 120 (стандартный)
- Масочная защита: резкость применяется только внутри `subject_mask`
- **Face skin overshoot limit** (v6.4): если доступна `face_skin_mask`, пиксели внутри неё не могут превысить `white_ceiling + face_overshoot_limit` (default: 8–10 уровней). Это предотвращает «звенящий» пересвет на коже лица при агрессивной резкости, сохраняя детализацию в одежде

### 7a. Safety Cap (face_skin soft rolloff перед gamma)

**Встроен в:** `retouch/processing/core/steps.py`

Если `stone_gamma < 1.0` (осветляющая gamma) и доступна `face_skin_mask`:
1. Вычисляется `knee = white_ceiling × 0.90`
2. Вычисляется `safe_post_gamma = knee - FACE_SKIN_KNEE_MARGIN (10 уровней)`
3. Обратный расчёт: `max_pre_gamma = (safe_post_gamma / 255)^(1/gamma) × 255`
4. Пиксели face_skin выше `soft_knee_start = max_pre_gamma - 5` плавно сжимаются (soft rolloff)

**Цель:** гарантировать, что после применения gamma лицо не попадёт в зону rolloff knee — иначе tonal variation лица будет сжата в серое плато. Safety cap применяется **после** unsharp (чтобы overshoot тоже был ограничен) и **до** postprocess (gamma + rolloff).

### 7b. Shadow Noise (impact only)

**Модуль:** `retouch/processing/correction/shadow_noise.py`

Для `machine_type == "impact"`: к пикселям с яркостью < `shadow_noise_threshold` (default: 30) **внутри маски субъекта** добавляется случайный шум в диапазоне `shadow_noise_min`–`shadow_noise_max` (default: 5–15). Шум добавляется только в субъект (`subject_dark = mask_bool & (arr < threshold)`), а не на фоне — это исправление бага A.1.

Это даёт игле impact-станка «зацепку» в полностью чёрных областях — без шума игла не бьёт в пиксели со значением 0.

### 8. Postprocess (shadow_floor + stone_gamma + white_ceiling + soft_rolloff)

**Модуль:** `retouch/processing/correction/postprocess.py`

`apply_postprocess()` — унифицированный шаг, объединяющий:
- **Shadow floor:** `np.maximum(arr, shadow_floor)` — предотвращает уход теней в 0. Для `laser_standard` и `laser_80w` shadow floor ограничен `face_mask` — применяется только к коже лица, не затрагивая волосы и одежду (v6.4 fix)
- **Stone gamma:** `apply_stone_gamma_masked()` — гамма-коррекция (< 1.0 осветляет, > 1.0 затемняет)
- **White ceiling + soft rolloff:** `soft_rolloff_masked()` — плавное сжатие яркости в зоне highlights. Заменяет hard clamp `np.clip` — сохраняет текстуру в зоне пересвета. Rolloff применяется к `highlights` и `face_skin` зонам (v6.5), не ко всему subject

#### Двухпроходный postprocess

Postprocess выполняется в два прохода с gate check между ними:

1. **Pass 1** (пробный): `apply_postprocess()` с текущими параметрами
2. **Gate check**: замер `face_skin p95` до и после. Если per-step shift ≥ `face_skin_p95_shift_threshold` → gate сработал
3. **Pass 2** (при необходимости): `stone_gamma` ослабляется до `1.0 + (gamma - 1.0) × 0.5`, postprocess повторяется

Это предотвращает «перекоррекцию» — когда gamma слишком сильно сдвигает лицо, gate автоматически ослабляет gamma и пересчитывает результат.

### 8a. Highlight Rolloff (профиль preserve)

Для профиля `preserve` вместо полного postprocess применяется только `highlight_rolloff`:
- `build_face_safe_rolloff_mask()` создаёт маску только для `highlights` зоны (не face_skin)
- `soft_rolloff_masked()` плавно сжимает яркие пиксели
- Без gamma, без shadow_floor — минимальное вмешательство в исходную AI-ретушь

### 9. Арховая виньетка

**Модуль:** `retouch/processing/output/vignette.py`

- Рисует эллипс на чёрной маске, вынесенный выше изображения (headroom)
- Размывает край Gaussian Blur
- Композитит обработанное изображение поверх чёрного фона через виньеточную маску
- Параметры: vertical_offset, vertical_diameter, blur_radius, headroom, horizontal_oversize
- Можно отключить через `vignette.enabled: false` в config.yaml

См. [guides/vignette.md](../guides/vignette.md).

### 10. Валидация результата

**Модуль:** `retouch/validation/image.py`

- Проверяет: доля чёрного фона >= `result_min_black_ratio` (default: 25%)
- Если меньше — результат некорректный (субъект занимает почти всё изображение)

### 11. Сохранение BMP/PNG

**Модуль:** `retouch/processing/output/export.py`

- **BMP** — основной формат для ЧПУ станков (v3: формат по export_mode):
  - Все машины по умолчанию (export_mode='8bit'): 8-bit grayscale BMP (256 оттенков, палитра R=G=B)
  - При export_mode='1bit': 1-bit монохромный BMP с Jarvis/Stucki дизерингом
  - DPI в заголовке BMP: dpi = 25.4 / step_mm (Engrave не использует, но предупреждает при несовпадении)
- **PNG** — автоматически для визуальной проверки (превью)
- TIFF доступен через `--format tiff` (legacy)

### 11a. BMP Post-Validation (F.3)

**Встроен в:** `retouch/processing/core/pipeline.py`

Автоматическая проверка после сохранения: `_validate_export()` проверяет что mode и size сохранённого BMP совпадают с ожидаемыми. Гарантирует целостность выходного файла для ЧПУ станка.

### 11b. Dither Preview (v6.0)

**Эндпоинт:** `POST /api/process/dither-preview`

Предпросмотр дизеринга — отдельный API-вызов, не часть `/process/preview`. Доступен для **всех машин** — показывает результат 1-bit растрирования, чтобы оператор мог оценить переключение с 8-bit на 1-bit.

- Вызывается по кнопке «Просмотр дизеринга» в StepSelector
- Метод дизеринга берётся из конфига станка (dither_method_1bit): jarvis для лазеров, stucki для impact
- Без Numba: 30-120 сек. С Numba: ~1-2 сек
- Без Numba — подтверждение через `confirm()` в UI
- Результат — base64 PNG с дизеринг-изображением, отображается как шаг «Dithered» в StepSelector
- Таймаут: 180 сек без Numba, 30 сек с Numba

---

## PipelineContext (B.1)

**Модуль:** `retouch/processing/core/context.py`

`PipelineContext` dataclass — внутренняя упаковка параметров пайплайна (только внутри `pipeline.py` и `steps.py`). Публичный API функций обработки НЕ меняется — они сохраняют текущие сигнатуры.

Поля:
- `img_gray`, `img_chromakey`, `subject_mask`, `face_mask`, `hair_mask` — изображения и маски
- `hair_anomaly`, `hair_ratio` — диагностика hair-зоны (v6.4)
- `analytics` — ImageAnalytics или dict
- `machine_type`, `config`, `machine_cfg`, `stone_type`, `step_mm` — параметры конфигурации
- `face_brightness_before`, `face_brightness_after`, `correction_factor`, `face_brightness_delta` — диагностические метрики
- `face_skin_variance_before` — variance face_skin до коррекции
- `warnings`, `debug_dir` — предупреждения и директория отладки

`PipelineResult` содержит все промежуточные изображения, метрики качества (F.2: `clipped_pixels_pct`, `shadow_crush_pct`, `tonal_range_output`, `quality_warnings`), параметры овала лица (`face_oval` — для передачи preview → export без повторной детекции), диагностику hair-зоны (`hair_mask`, `hair_anomaly`, `hair_ratio`), step-метрики (`step_metrics`), plan (`plan`, `validated_plan`), zone masks (`zone_masks`), gate state (`gate_state`) и метод `release_intermediates()` для освобождения памяти.

---

## Принятие решений

### PipelinePlan

**Модуль:** `retouch/processing/core/plan.py`

Структурированное описание плана обработки:
- `PipelinePlan` — активные шаги, параметры (skin_delta, glow_size, unsharp_*, stone_gamma, shadow_floor, white_ceiling)
- `SafetyEnvelope` — лимиты коррекций по зонам: `face_skin ±15`, `face_dark ±5`, `hair ±3`, `clothes 0`. Настраивается через `safety_envelope` секцию в config.yaml
- `ValidatedPlan` — результат `validate_plan()` с флагами нарушений, отключёнными шагами, клипнутыми параметрами
- Профили: `standard` (все шаги), `preserve` (только chromakey → gray → glow → highlight_rolloff → vignette), `diagnostic` (с сохранением масок и метрик)

### ZoneMetrics

**Модуль:** `retouch/processing/analysis/metrics.py`

Метрики по зонам после каждого шага обработки:
- `ZoneMetrics` — median, mean, p10, p90, p95, max, variance, clipped_pct для каждой зоны
- `StepMetricsRecord` — снимок метрик после конкретного шага пайплайна + timestamp + warnings
- `compute_zone_metrics()` — вычисление метрик по `ZoneMasks`

### Quality Gates

**Модуль:** `retouch/processing/core/gates.py`

Контрольные точки качества пайплайна:

**Pre-check (2):**

| Gate | Функция | Триггер | Действие |
|------|---------|---------|----------|
| `face_dark_small` | `pre_check_face_dark_small()` | face_dark < 5% от face_mask | Пропустить коррекцию |
| `contour_inner_quality` | `pre_check_contour_inner_quality()` | contour_inner > 30% субъекта | Fallback на morphological contour |

**Post-check (5):**

| Gate | Функция | Триггер | Действие |
|------|---------|---------|----------|
| `variance_loss` | `post_check_variance_loss()` | потеря variance face_skin > 35% | Ослабить stone_gamma на 50% |
| `clipped_pct` | `post_check_clipped_pct()` | клиппинг face_skin > 5% | Увеличить rolloff compression на 20% |
| `p95_shift` | `post_check_p95_shift()` | сдвиг face_skin p95 > порога (3.0 laser, 5.0 impact) | Ослабить stone_gamma на 50% |
| `p95_shift_cumulative` | `post_check_p95_shift(gate_name=...)` | cumulative сдвиг face_skin p95 > порога | Diagnostic only (warning) |
| `shadow_crush` | `post_check_shadow_crush()` | crush теней > 10% | Отключить shadow_floor и stone_gamma |

Каждый gate возвращает `GateResult(gate_name, step_name, triggered, original_value, adjusted_value, reason)`. `gate_state` в `PipelineResult` — сводка всех gate'ов.

### Gates Enforcement

**Модуль:** `retouch/processing/core/gates_enforcement.py`

`enforce_gates()` применяется после unsharp, до postprocess. Порядок ослабления:

1. **shadow_crush** (P1.3, экстренный): сбрасывает `shadow_floor = 0` и `stone_gamma = 1.0`. Проверяется первым — если тени раздавлены, остальные ослабления бессмысленны
2. **variance_loss / p95_shift**: ослабляют `stone_gamma` до `1.0 + (gamma - 1.0) × 0.5` (single-pass, не кумулятивно). Если shadow_crush уже сбросил gamma — пропускается
3. **p95_shift_cumulative**: diagnostic only — добавляет warning, НЕ ослабляет gamma
4. **clipped_pct**: увеличивает `rolloff_compression` на 20% (max 0.80)

Пороги настраиваются через `quality_gates` секцию в config.yaml. Per-machine переопределения: `face_skin_p95_shift_threshold_by_machine`.

### Soft Rolloff

**Модуль:** `retouch/processing/correction/rolloff.py`

Унифицированная функция `soft_rolloff_masked(arr, mask, knee, ceiling, compression)`:
- Плавное сжатие яркости в зоне highlights (soft knee)
- Заменяет inline `np.clip` — сохраняет текстуру в зоне пересвета
- Используется в postprocess и face_brightness
- `build_face_safe_rolloff_mask()` — строит маску для rolloff: `highlights` зона (основная) + `face_skin` (v6.5), исключая face_dark, hair, clothes

---

## Диагностика проблем

### Портрет пересвечен

Причина: `face_brightness_target` слишком высокий, или адаптивный фактор даёт слишком большое усиление.

Решение:
1. Понизить `face_brightness_target` (напр. [100, 130] вместо [200, 225])
2. Установить `stone_gamma: 1.00`
3. Проверить что glow не завышает замер (маска сжимается на glow_size)
4. Проверить gate_state — если `p95_shift` сработал, gamma ослаблена автоматически

### Воротник пересвечен

Причина: коррекция яркости применялась ко всему изображению без маски. Начиная с v5.0.0 маска лица из овала (C.3) ограничивает замер зоной лица — воротник исключается.

Решение: убедитесь, что `face_mask` передаётся в `face_brightness_correction()`. Если проблема остаётся — понизить `face_brightness_target`.

### Белый фон (не чёрный)

Причина: хромакей не обнаружен, синий фон не удалён.

Решение: проверить `blue_threshold` и `min_blue_ratio`. Понизить порог или использовать `--no-validate`.

### Серая дымка на фоне

Причина: коррекция яркости или резкость «задела» фоновые пиксели. Исправлено масочной защитой (шаг 6a).

Решение: убедитесь, что `subject_mask` передаётся в `face_brightness_correction()` и `apply_unsharp_mask()`.

### Голова обрезана виньеткой

Причина: `headroom` слишком маленький.

Решение: увеличить `headroom` в config.yaml (напр. 0.8 вместо 0.6).

### Glow различается между preview и export

Причина: до v5.0.0 glow рандомизировался, давая разный результат при каждом запуске.

Решение: обновлено до v5.0.0 — glow детерминирован (D.1), preview и export дают одинаковый результат.

### Лицо серое плоское после postprocess

Причина: face_skin попал в зону rolloff knee — tonal variation сжалась в серое плато.

Решение: safety cap (шаг 7a) предотвращает это автоматически. Если проблема остаётся — проверьте `face_skin_p95_shift_threshold` в quality_gates, возможно gamma слишком агрессивная и gate не успевает сработать.

### Gate срабатывает постоянно

Причина: параметры слишком агрессивные для данного фото.

Решение: проверить `gate_state` в diagnostics — какой gate triggered и почему. Увеличить порог или использовать профиль `preserve`.
