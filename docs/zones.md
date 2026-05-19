# Зональное разделение (ZoneMasks)

## Обзор

Пайплайн разделяет изображение на технические зоны для дифференцированной обработки. Это не семантическая сегментация — это рабочие маски, достаточные чтобы не применять одну коррекцию ко всему портрету.

## Зоны

| Зона | Формула | Описание |
|------|---------|----------|
| `face_skin` | `face_mask & subject_mask & gray >= skin_threshold` | Кожа лица |
| `face_dark` | `face_mask & subject_mask & gray < skin_threshold` | Тёмные участки лица (брови, тени) |
| `hair` | `subject_mask выше овала лица` | Волосы (approximate) |
| `clothes` | `subject_mask & ~face_mask & ~hair_mask` | Одежда |
| `highlights` | `subject_mask & gray >= highlight_threshold` | Светлые зоны субъекта |
| `contour_inner` | внутренний край субъекта | Для glow и сохранения плотности |
| `contour_outer` | внешний переход в фон | Для антифринги |
| `background` | `~subject_mask` | Фон (хромакей) — без коррекций |

## Приоритет зон

Пересечения разрешаются по фиксированному приоритету:

```
highlights > face_skin > face_dark > hair > clothes > contour
```

Каждый пиксель получает одну основную коррекцию по самой приоритетной зоне. `resolve_zone_priority()` гарантирует дизъюнктность — все `final_*` маски не пересекаются.

## Адаптивный skin threshold

Абсолютный `skin_threshold=100` слишком хрупкий для тёмной кожи, бороды и бокового света.

**Двухпроходная формула:**
```
coarse_skin = face_pixels where gray >= absolute_skin_min
robust_face_center = histogram_mode(coarse_skin)  # smoothed
adaptive_threshold = clamp(robust_face_center - delta, min_value, max_value)
```

`histogram_mode` реализуется через `np.bincount()` + сглаживание `np.convolve(hist, [0.25, 0.5, 0.25])`.

## Beard detection

Если `face_dark > 40%` от `face_mask`:
1. Spatial check: >60% `face_dark` должны быть в нижней трети овала
2. При равномерном распределении (тёмная кожа без бороды) — не считается бородой
3. Пиксели `face_dark` в нижней троти переклассифицируются в `hair`
4. Diagnostics: `beard_suspected=True`, `beard_reclassified_pixels=N`

## Safety envelope

Максимальная допустимая дельта коррекции по зонам:

| Зона | Max delta |
|------|-----------|
| `face_skin` | ±15 |
| `face_dark` | ±5 |
| `hair` | ±3 |
| `clothes` | 0 |
| `highlights` | только rolloff, без подъёма |

Значения эмпирические (±15 на 256-шкале ≈ 6%, едва заметно на гравировке). Доступны для override через `config.yaml` (секция `safety_envelope`).

## Контур из gradient mask

```python
gradient = chromakey_gradient_mask  # float 0..1
contour_inner = (gradient > 0.5) & (gradient < 1.0)
contour_outer = (gradient > 0.0) & (gradient <= 0.5)
```

**Fallback:** если `contour_inner > 30%` от `subject_mask` — morphological contour (`dilate - erode`) с warning `contour_fallback_used`.

## Bounded delta

Агрессивная коррекция по зонам ограничивается safety envelope. Формула bounded delta:

```
delta = clamp(target - median, -max_delta, +max_delta)
```

где `max_delta` — значение из таблицы Safety Envelope (см. выше) или из `config.yaml:processing.safety_envelope.<zone_name>`.

**Механизм:**
1. `bounded_delta()` вычисляет сырую дельту как `target - median`
2. Клиппит по `[-max_delta, +max_delta]`
3. Возвращает `(delta, clamped)` — clamped=true если сработала оболочка
4. Проверяется gate `skin_delta_envelope` — если `|delta| > max_delta`, warning в diagnostics

**Вес коррекции (curves):**

После bounded delta применяется `_curves_correction()`:

```
weight = 1.0 - (pixel_norm - highlight_start_norm) / (1.0 - highlight_start_norm)
correction = pixel + delta * clamp(weight, 0, 1)
```

- Тени (`pixel < highlight_start`) получают полную коррекцию
- Света (`pixel > highlight_start`) получают уменьшенную коррекцию (защита пересветов)

## Rolloff (soft knee)

Вместо hard clamp `np.clip()` используется `soft_rolloff_masked()` — плавное сжатие светов.

**Формула:**

```python
excess = max(value - knee, 0)          # пересвет
rolloff = excess * (1 - compression)   # сжатие
output = knee + rolloff                # результат
```

где:
- `knee` — порог срабатывания (по умолч. 200, из `config.yaml:rolloff_knee`)
- `compression` — сила сжатия (по умолч. 0.35, из `config.yaml:rolloff_compression`)
- компрессия = 0 → hard clip, компрессия = 1 → без изменений

**Применение по зонам (v6.5):**

Rolloff применяется только к `highlights` зоне (не ко всему subject):
- Если ZoneMasks доступны → rolloff по `highlights` + `face_skin`
- Если ZoneMasks недоступны → fallback на `subject_mask`

**Gate: `clipped_pct`**

Пост-чек: если >5% пикселей достигли white_ceiling → `compression` увеличивается на 20% (автоматическое ослабление).

## Memory budget

| Разрешение | Budget на маски |
|------------|-----------------|
| Preview (≤1920px) | ≤128 MB |
| Export (≤8K) | ≤1200 MB (single-pass) |

Маски хранятся как `uint8` (bool через `astype` только в момент операции). После `resolve_zone_priority()` ненужные исходные маски удаляются.
