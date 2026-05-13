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
- Синий хромакей: >= `min_blue_ratio` (default: 15%) синих пикселей

Ошибка → `ValidationError` + exit 1.

### 2. Загрузка и конвертация в RGBA

```python
img = Image.open(input_path).convert("RGBA")
```

### 3. Удаление синего хромакея + fringe removal + градиентная маска

**Модуль:** `retouch/processing/chromakey.py`

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

### 4a. Преданализ (analytics)

**Модуль:** `retouch/processing/analysis.py`

После конвертации в grayscale pipeline измеряет 13 метрик входного изображения внутри маски субъекта:

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

### 4b. Детекция зоны лица (C.1)

**Модуль:** `retouch/processing/face_region.py`

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

### 4c. Генерация маски лица и волос из овала (C.2)

**Модуль:** `retouch/processing/face_region.py`

- `generate_face_mask(width, height, face_oval, subject_mask)` — создаёт эллипс по овалу ∩ subject_mask. Если `face_oval` не задан — legacy fallback (верхние 45%)
- `generate_hair_mask(face_mask, subject_mask, gap_ratio=0.05)` — маска волос = субъект выше овала лица с зазором `gap_ratio` (доля высоты изображения)

Маска лица точнее, чем топологический `face_region_top` — овал ограничивает замер яркости зоной лица, исключая лоб/волосы/шею.

### 5. Glow (inner | outer, детерминированный)

**Модуль:** `retouch/processing/glow.py`

Параметры glow **детерминированы** (D.1): при наличии analytics — midpoint адаптивного диапазона через `_calculate_glow_params()`, без analytics — midpoint диапазона из конфига. Рандомизация полностью устранена для preview-export consistency.

Стиль glow задаётся параметром `glow_style` в конфиге:
- **`inner`** — свечение внутрь (настоящий inner glow через `apply_inner_glow_algorithm()`: shrink→edge→blur→composite). Ярче у внутреннего края субъекта, затухает к центру
- **`outer`** — свечение наружу (классический glow, `apply_outer_glow()`). Инвертированная маска → blur → composite

Диспетчер `apply_glow()` выбирает реализацию по `glow_style`.

Параметры зависят от типа станка и аналитики:
- **Laser Standard:** glow 40–80px, opacity 30–40% (широкий, мягкий)
- **Laser 80W:** фиксированные параметры (20, 15) — мощный лазер сам создаёт контраст. Glow фиксирован на середине диапазона для обеспечения детерминированности (D.1).
- **Impact:** параметры зависят от `subject_separation` и `tonal_range` — при низкой сепарации glow усиливается

### 6. Levels (яркость)

**Модуль:** `retouch/processing/levels.py`

Фактор яркости вычисляется из analytics (адаптивный режим):
- `target_pre_fb`: laser_standard=210, laser_80w=170, impact=180
- `factor = target_pre_fb / median_brightness`, ограничен диапазоном [0.70, 1.35]
- Защита от клиппинга: если `p90 * factor > 250` → фактор снижается
- Без analytics — legacy mode (фиксированный `brightness_factor` из конфига)

### 6a. Масочная защита

`apply_levels()` и `apply_unsharp_mask()` принимают `subject_mask`. Пиксели вне маски (фон) остаются без изменений — предотвращает серую дымку на чёрном фоне и halo на границе субъект/фон. Это критично: после хромакея фон должен быть абсолютно чёрным (~0), и любая коррекция яркости или резкости за пределами маски субъекта создаёт видимые артефакты на готовой гравировке.

### 7. Face Brightness (по маске лица)

**Модуль:** `retouch/processing/face_correction.py` → `check_face_brightness()`

Начиная с этапа C.3, `check_face_brightness()` принимает `face_mask_img` (маску лица из овала) вместо топологического `face_region_top`. Маска лица точнее — овал ограничивает замер яркости зоной лица, исключая лоб/волосы/шею.

- Сжимает маску лица на `glow_size` пикселей (исключает внутренний контур свечения из замера)
- Измеряет среднюю яркость по сжатой маске
- Если вне диапазона `face_brightness_target`:
  - Вычисляет correction factor: `target_mid / current_avg`
  - Ограничивает: `max(0.60, min(1.40, correction))`
  - Применяет **нелинейную (curves) коррекцию**: тени корректируются полностью, света минимально
  - Это поднимает лицо (тёмное) без пересвета воротника (светлого)
- Масочная защита: коррекция применяется только внутри `subject_mask`
- Целевые диапазоны по типу станка:
  - **Laser Standard:** 230–245, white_ceiling: 250, highlight_start: 210
  - **Laser 80W:** 190–210, white_ceiling: 235, highlight_start: 195
  - **Impact:** 200–225, white_ceiling: 240, highlight_start: 200
- **highlight_start** теперь вычисляется по формуле `white_ceiling - 40`, чтобы коррекция уровней плавно затухала только после достижения целевой яркости лица. Это гарантирует, что яркое лицо не будет «задушено» защитой от пересвета слишком рано.

### 8. Unsharp Mask (адаптивный)

**Модуль:** `retouch/processing/unsharp.py`

Порядок шагов изменён (A.3): unsharp mask теперь **ПОСЛЕ** face_brightness correction. Старый порядок доступен через `legacy_step_order: true` в config.yaml.

- `ImageFilter.UnsharpMask(radius=1.5, percent=<adaptive>, threshold=0)`
- Адаптивный percent зависит от analytics:
  - `overbright` → 80 (сниженный — пересвету резкость не нужна)
  - `tonal_range < 40` → 150 (усиленный — узкий диапазон требует чёткости)
  - Норма → 120 (стандартный)
- Масочная защита: резкость применяется только внутри `subject_mask`

### 8a. Shadow Noise (impact)

**Модуль:** `retouch/processing/shadow_noise.py`

Для `machine_type == "impact"`: к пикселям с яркостью < `shadow_noise_threshold` (default: 30) **внутри маски субъекта** добавляется случайный шум в диапазоне `shadow_noise_min`–`shadow_noise_max` (default: 5–15). Шум добавляется только в субъект (`subject_dark = mask_bool & (arr < threshold)`), а не на фоне — это исправление бага A.1.

Это даёт игле impact-станка «зацепку» в полностью чёрных областях — без шума игла не бьёт в пиксели со значением 0.

### 8b. Shadow Floor (impact)

**Встроен в:** `retouch/processing/pipeline.py`

Отдельный шаг для impact: `np.maximum(arr, shadow_floor)`. Предотвращает уход теней в 0 — игла застревает на чистом чёрном. Shadow floor — machine-specific логика, вынесена из `_curves_correction()` чтобы не нарушать SRP.

### 8c. White Ceiling Clamp

**Встроен в:** `retouch/processing/pipeline.py`

Hard clamp: `np.clip(arr, 0, white_ceiling)` перед виньеткой. После shadow_noise и виньетки могут появиться пиксели > white_ceiling — clamp гарантирует что ни один пиксель (кроме зрачков) не превышает потолок.

### 9. Арховая виньетка

**Модуль:** `retouch/processing/vignette.py`

- Рисует эллипс на чёрной маске, вынесенный выше изображения (headroom)
- Размывает край Gaussian Blur
- Композитит обработанное изображение поверх чёрного фона через виньеточную маску
- Параметры: vertical_offset, vertical_diameter, blur_radius, headroom, horizontal_oversize

См. [guides/vignette.md](../guides/vignette.md).

### 10. Валидация результата

**Модуль:** `retouch/validation/image.py`

- Проверяет: доля чёрного фона >= `result_min_black_ratio` (default: 25%)
- Если меньше — результат некорректный (субъект занимает почти всё изображение)

### 11. Сохранение BMP/PNG

**Модуль:** `retouch/processing/export.py`

- **BMP** — основной формат для ЧПУ станков:
  - laser_standard: 8-bit grayscale BMP (256 оттенков, палитра R=G=B)
  - laser_80w: 1-bit монохромный BMP с Jarvis дизерингом
  - impact: 8-bit grayscale BMP (256 уровней силы удара ударного станка)
- **PNG** — автоматически для визуальной проверки (превью)
- TIFF доступен через `--format tiff` (legacy)

### 11a. BMP Post-Validation (F.3)

**Встроен в:** `retouch/processing/pipeline.py`

Автоматическая проверка после сохранения: `_validate_export()` проверяет что mode и size сохранённого BMP совпадают с ожидаемыми. Гарантирует целостность выходного файла для ЧПУ станка.

### 11b. Dither Preview (v6.0)

**Эндпоинт:** `POST /api/process/dither-preview`

Предпросмотр Jarvis дизеринга — отдельный API-вызов, не часть `/process/preview`. Доступен только для `laser_80w`.

- Вызывается по кнопке «Просмотр дизеринга» в StepSelector
- Без Numba: 30-120 сек. С Numba: ~1-2 сек
- Без Numba — подтверждение через `confirm()` в UI
- Результат — base64 PNG с дизеринг-изображением, отображается как шаг «Dithered» в StepSelector
- Таймаут: 180 сек без Numba, 30 сек с Numba

---

## PipelineContext (B.1)

**Модуль:** `retouch/processing/pipeline.py`

`PipelineContext` dataclass — внутренняя упаковка параметров пайплайна (только внутри `pipeline.py`). Публичный API функций обработки НЕ меняется — они сохраняют текущие сигнатуры.

Поля:
- `img_gray`, `subject_mask`, `face_mask`, `hair_mask` — изображения и маски
- `analytics` — ImageAnalytics или dict
- `machine_type`, `config`, `stone_type`, `stone_heterogeneity`, `step_mm` — параметры конфигурации
- `face_brightness_before`, `face_brightness_after`, `correction_factor` — диагностические метрики
- `img_chromakey` — промежуточное RGBA-изображение после хромакея (отклонение от плана: сохранено для preview и диагностики)

`PipelineResult` содержит все промежуточные изображения, метрики качества (F.2: `clipped_pixels_pct`, `shadow_crush_pct`, `tonal_range_output`, `quality_warnings`), параметры овала лица (`face_oval` — для передачи preview → export без повторной детекции) и метод `release_intermediates()` для освобождения памяти.

---

## Диагностика проблем

### Портрет пересвечен

Причина: `face_brightness_target` слишком высокий, или адаптивный фактор даёт слишком большое усиление.

Решение:
1. Понизить `face_brightness_target` (напр. [100, 130] вместо [200, 225])
2. Установить `brightness: 1.00`
3. Проверить что glow не завышает замер (маска сжимается на glow_size)

### Воротник пересвечен

Причина: коррекция яркости применялась ко всему изображению без маски. Начиная с v5.0.0 маска лица из овала (C.3) ограничивает замер зоной лица — воротник исключается.

Решение: убедитесь, что `face_mask` передаётся в `check_face_brightness()`. Если проблема остаётся — понизить `face_brightness_target`.

### Белый фон (не чёрный)

Причина: хромакей не обнаружен, синий фон не удалён.

Решение: проверить `blue_threshold` и `min_blue_ratio`. Понизить порог или использовать `--no-validate`.

### Серая дымка на фоне

Причина: коррекция яркости или резкость «задела» фоновые пиксели. Исправлено масочной защитой (шаг 6a).

Решение: убедитесь, что `subject_mask` передаётся в `apply_levels()` и `apply_unsharp_mask()`.

### Голова обрезана виньеткой

Причина: `headroom` слишком маленький.

Решение: увеличить `headroom` в config.yaml (напр. 0.8 вместо 0.6).

### Glow различается между preview и export

Причина: до v5.0.0 glow рандомизировался, давая разный результат при каждом запуске.

Решение: обновлено до v5.0.0 — glow детерминирован (D.1), preview и export дают одинаковый результат.
