# Пайплайн обработки

Полный конвейер обработки портрета: от PNG с синим хромакеем до TIFF с чёрным фоном.

Запуск: `python -m retouch process -i ai.png -o final.tiff -m laser`

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

### 5. Inner Glow (контурный свет)

**Модуль:** `retouch/processing/glow.py`

- Инвертирует маску субъекта → blur (glow_size) → multiply с оригинальной маской → scale по opacity
- Композитит белое свечение поверх grayscale изображения
- Параметры зависят от типа станка:
  - **Laser:** glow 40–80px, opacity 30–40% (широкий, мягкий)
  - **Impact:** glow 10–25px, opacity 60–80% (узкий, яркий)
- Размер и opacity рандомизируются в заданном диапазоне

### 6. Levels (яркость)

**Модуль:** `retouch/processing/levels.py`

- Применяет `ImageEnhance.Brightness` с `brightness_factor` из конфига
- Laser: 1.18 (немного ярче), Impact: 1.00 (без изменения)

### 7. Unsharp Mask

**Модуль:** `retouch/processing/levels.py`

- `ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=0)`
- Добавляет резкость — критично для станка

### 8. Контроль яркости лица

**Модуль:** `retouch/processing/levels.py` → `check_face_brightness()`

- Сжимает маску субъекта на `glow_size` пикселей (исключает внутренний контур свечения из замера)
- Измеряет среднюю яркость по сжатой маске
- Если вне диапазона `face_brightness_target`:
  - Вычисляет correction factor: `target_mid / current_avg`
  - Ограничивает: `max(0.60, min(1.40, correction))`
  - Применяет **нелинейную (curves) коррекцию**: тени корректируются полностью, света минимально
  - Это поднимает лицо (тёмное) без пересвета воротника (светлого)
- Laser target: 230–245, Impact target: 185–210

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

- TIFF: без сжатия (для станка)
- PNG: автоматически (для превью)

---

## Диагностика проблем

### Портрет пересвечен

Причина: `face_brightness_target` слишком высокий, или `brightness` > 1.0.

Решение:
1. Понизить `face_brightness_target` (напр. [100, 130] вместо [185, 210])
2. Установить `brightness: 1.00`
3. Проверить что inner glow не завышает замер (маска сжимается на glow_size)

### Воротник пересвечен

Причина: коррекция яркости применяется ко всему изображению, а не только к области лица.

Решение: понизить `face_brightness_target` чтобы коррекция не требовалась. См. BACKLOG-002.

### Белый фон (не чёрный)

Причина: хромакей не обнаружен, синий фон не удалён.

Решение: проверить `blue_threshold` и `min_blue_ratio`. Понизить порог или использовать `--no-validate`.

### Голова обрезана виньеткой

Причина: `headroom` слишком маленький.

Решение: увеличить `headroom` в config.yaml (напр. 0.8 вместо 0.6).
