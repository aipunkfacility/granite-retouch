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

### 3. Удаление синего хромакея + fringe removal

**Модуль:** `retouch/processing/chromakey.py`

- Определяет синие пиксели: `B > R + threshold` и `B > G + threshold`
- Заменяет синие пиксели на прозрачные `[0, 0, 0, 0]`
- Fringe removal: расширяет маску на `fringe_radius` пикселей (scipy binary_dilation) и плавно гасит синий канал в переходной зоне
- Выход: изображение RGBA (без фона) + маска субъекта L (255 = субъект)

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

Результат передаётся во все последующие шаги (Glow, Levels, Unsharp). Если numpy недоступен — используется legacy mode с фиксированными параметрами из конфига.

### 5. Inner Glow (контурный свет)

**Модуль:** `retouch/processing/glow.py`

- Инвертирует маску субъекта → blur (glow_size) → multiply с оригинальной маской → scale по opacity
- Композитит белое свечение поверх grayscale изображения
- Параметры зависят от типа станка и аналитики:
  - **Laser Standard:** glow 40–80px, opacity 30–40% (широкий, мягкий)
  - **Laser 80W:** фиксированные параметры (20, 15) — мощный лазер сам создаёт контраст, усиление не нужно
  - **Impact:** параметры зависят от `subject_separation` и `tonal_range` — при низкой сепарации glow усиливается
- Размер и opacity рандомизируются в заданном диапазоне (кроме laser_80w)

### 6. Levels (яркость)

**Модуль:** `retouch/processing/levels.py`

Фактор яркости вычисляется из analytics (адаптивный режим):
- `target_pre_fb`: laser_standard=210, laser_80w=190, impact=190
- `factor = target_pre_fb / median_brightness`, ограничен диапазоном [0.70, 1.35]
- Защита от клиппинга: если `p90 * factor > 250` → фактор снижается
- Без analytics — legacy mode (фиксированный `brightness_factor` из конфига)

### 6a. Масочная защита

`apply_levels()` и `apply_unsharp_mask()` принимают `subject_mask`. Пиксели вне маски (фон) остаются без изменений — предотвращает серую дымку на чёрном фоне и halo на границе субъект/фон. Это критично: после хромакея фон должен быть абсолютно чёрным (~0), и любая коррекция яркости или резкости за пределами маски субъекта создаёт видимые артефакты на готовой гравировке.

### 7. Unsharp Mask

**Модуль:** `retouch/processing/levels.py`

- `ImageFilter.UnsharpMask(radius=1.5, percent=<adaptive>, threshold=0)`
- Адаптивный percent зависит от analytics:
  - `overbright` → 80 (сниженный — пересвету резкость не нужна)
  - `tonal_range < 40` → 150 (усиленный — узкий диапазон требует чёткости)
  - Норма → 120 (стандартный)
- Масочная защита: резкость применяется только внутри `subject_mask`

### 8. Контроль яркости лица

**Модуль:** `retouch/processing/levels.py` → `check_face_brightness()`

- Сжимает маску субъекта на `glow_size` пикселей (исключает внутренний контур свечения из замера)
- Измеряет среднюю яркость по сжатой маске
- Если вне диапазона `face_brightness_target`:
  - Вычисляет correction factor: `target_mid / current_avg`
  - Ограничивает: `max(0.60, min(1.40, correction))`
  - Применяет **нелинейную (curves) коррекцию**: тени корректируются полностью, света минимально
  - Это поднимает лицо (тёмное) без пересвета воротника (светлого)
- Масочная защита: коррекция применяется только внутри `subject_mask`
- Целевые диапазоны по типу станка:
  - **Laser Standard:** 230–245, white_ceiling: 250
  - **Laser 80W:** 190–210, white_ceiling: 235
  - **Impact:** 200–225, white_ceiling: 240

### 8a. Shadow noise (impact)

**Модуль:** `retouch/processing/levels.py` → `add_shadow_noise()`

Для `machine_type == "impact"`: к пикселям с яркостью < 30 внутри маски субъекта добавляется случайный шум в диапазоне `shadow_noise_min`–`shadow_noise_max` (default: 5–15). Это даёт игле impact-станка «зацепку» в полностью чёрных областях — без шума игла не бьёт в пиксели со значением 0 (нечего выбить на камне).

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

### 11. Сохранение

- **BMP** — основной формат для ЧПУ станков:
  - laser_standard / impact: 8-bit grayscale BMP (256 оттенков, палитра R=G=B)
  - laser_80w: 1-bit монохромный BMP с Floyd-Steinberg дизерингом
- **PNG** — автоматически для визуальной проверки (превью)
- TIFF доступен через `--format tiff` (legacy)

См. [reference/config.md](../reference/config.md) — секция export.

---

## Диагностика проблем

### Портрет пересвечен

Причина: `face_brightness_target` слишком высокий, или адаптивный фактор даёт слишком большое усиление.

Решение:
1. Понизить `face_brightness_target` (напр. [100, 130] вместо [200, 225])
2. Установить `brightness: 1.00`
3. Проверить что inner glow не завышает замер (маска сжимается на glow_size)

### Воротник пересвечен

Причина: коррекция яркости применялась ко всему изображению без маски. В v4.0 это исправлено масочной защитой (шаг 6a).

Решение: убедитесь, что `subject_mask` передаётся в `apply_levels()` и `check_face_brightness()`. Если проблема остаётся — понизить `face_brightness_target`.

### Белый фон (не чёрный)

Причина: хромакей не обнаружен, синий фон не удалён.

Решение: проверить `blue_threshold` и `min_blue_ratio`. Понизить порог или использовать `--no-validate`.

### Серая дымка на фоне

Причина: коррекция яркости или резкость «задела» фоновые пиксели. В v4.0 это исправлено масочной защитой.

Решение: убедитесь, что `subject_mask` передаётся в `apply_levels()` и `apply_unsharp_mask()`.

### Голова обрезана виньеткой

Причина: `headroom` слишком маленький.

Решение: увеличить `headroom` в config.yaml (напр. 0.8 вместо 0.6).
