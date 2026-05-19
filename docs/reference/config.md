# Справочник config.yaml

Все параметры обработки — в одном файле `config.yaml`. Если файл отсутствует — используются встроенные defaults.

Путь поиска: 1) аргумент `--config`, 2) `config.yaml` в корне проекта, 3) `config.yaml` в текущей директории, 4) встроенные defaults.

Приоритет параметров (B.2): UI params (сессия) > order.json (заказ) > config.yaml (базовый) > DEFAULTS.

---

## processing (общие)

| Параметр | Тип | Default | Диапазон | Описание |
|----------|-----|---------|----------|----------|
| `blue_threshold` | int | 30 | 10–80 | Порог определения синего хромакея. Пиксель считается синим если `B > R + threshold` и `B > G + threshold`. Больше → строже, меньше → захватывает тёмно-синюю одежду. **[Advanced — скрыт в UI по умолчанию]** |
| `min_blue_ratio` | float | 0.15 | 0.0–1.0 | Минимальная доля синих пикселей. Если ниже — хромакей не обнаружен, обработка прерывается. **[Advanced]** |
| `min_resolution` | int | 512 | 0–∞ | Минимальное разрешение (px по короткой стороне). 0 = без проверки. **[Advanced]** |
| `result_min_black_ratio` | float | 0.25 | 0.0–1.0 | Минимальная доля чёрного фона в результате. Если ниже — результат некорректный. **[Advanced]** |
| `fringe_radius` | int | 3 | 0–10 | Радиус расширения маски для fringe removal. Убирает синие рефлексы на краях субъекта. 0 = без fringe removal, 3 = стандарт, 5–10 = агрессивное. **[Advanced]** |
| `face_region_top` | float | 0.45 | 0.2–0.8 | Доля высоты маски субъекта сверху, которая считается «лицом» (legacy, заменено на face_mask из овала в C.3). **[Advanced]** |
| `highlight_start` | int | 210 | 80–250 | Яркость, начиная с которой применяется защита от пересвета (curves highlight protection). Рекомендуемая формула: `white_ceiling - 40`. **[Advanced]** |
| `shadow_noise_threshold` | int | 30 | 5–80 | Порог яркости для shadow noise: шум добавляется только в пиксели < threshold внутри маски субъекта |
| `mask_soft_sigma` | float | 1.5 | 0–5.0 | Ширина размытия краёв маски субъекта. 0 = бинарная маска (старое поведение). 1.0–2.0 = плавные края (рекомендуется). Размытие применяется к subject_mask, но не к альфа-каналу. **[Advanced]** |
| `contour_smooth_epsilon` | float | 0.002 | 0.0–0.01 | **DEPRECATED** — игнорируется. Градиентная маска хромакея не использует contour tracing. Параметр оставлен для совместимости. Ранее: параметр сглаживания через `cv2.approxPolyDP`. **[Advanced]** |
| `legacy_step_order` | bool | false | true/false | Использовать старый порядок шагов (unsharp ДО face_brightness). Для rollback без redeploy. **[Hidden — убран из UI, доступен только через config.yaml]** |

---

## Сводная таблица параметров по станкам

Все параметры, которые различаются между типами станков. Общие параметры (`blue_threshold`, `min_blue_ratio`, `fringe_radius` и т.д.) задаются на уровне `processing` и наследуются всеми станками.

| Параметр | `laser_standard` | `laser_80w` | `impact` |
|----------|:-----------------:|:-----------:|:--------:|
| `glow_size_min` | 40 | 15 | 10 |
| `glow_size_max` | 80 | 25 | 25 |
| `glow_opacity_min` | 30 | 10 | 60 |
| `glow_opacity_max` | 40 | 20 | 80 |
| `glow_style` | `"outer"` | `"outer"` | `"inner"` |
| `stone_gamma` | 0.88 | 1.0 | 0.88 |
| `unsharp_threshold` | 3 | 3 | 1 |
| `shadow_floor` | 5 | 5 | 2 |
| `target_pre_fb` | 180 | 150 | 160 |
| `face_brightness_target_min` | 230 | 160 | 170 |
| `face_brightness_target_max` | 245 | 180 | 215 |
| `white_ceiling` | 250 | 235 | 245 |
| `face_region_top` | 0.45 | 0.45 | 0.45 |
| `highlight_start` | 200 | 195 | 185 |
| `face_skin_threshold` | 100 | 100 | 100 |
| `shadow_noise_min` | — | — | 5 |
| `shadow_noise_max` | — | — | 15 |
| `shadow_noise_threshold` | — | — | 30 |
| `export_mode` | `"8bit"` | `"8bit"` | `"8bit"` |
| `step_mm` | 0.300 | 0.250 | 0.300 |
| `dither_method_1bit` | `"jarvis"` | `"jarvis"` | `"stucki"` |
| `dither_method` | `"none"` | `"none"` | `"none"` |
| `rolloff_compression` | 0.35 | 0.35 | 0.35 |

> Параметры, отмеченные `—`, не определены для данного станка (используется значение по умолчанию из `MachineConfig`).

---

## processing.laser_standard

Параметры для стандартной лазерной гравировки 20–40W (Mirtels, Stanzone).

| Параметр | Тип | Default | Диапазон | Описание |
|----------|-----|---------|----------|----------|
| `glow_size_min` | int | 40 | 5–100 | Минимальный размер Glow (px). Используется как диапазон для midpoint при отсутствии override: `glow_size = (min + max) // 2` |
| `glow_size_max` | int | 80 | 5–100 | Максимальный размер Glow (px) |
| `glow_opacity_min` | int | 30 | 10–100 | Минимальная opacity Glow (%). Midpoint: `(min + max) // 2` |
| `glow_opacity_max` | int | 40 | 10–100 | Максимальная opacity Glow (%) |
| `glow_style` | toggle | `"outer"` | `"inner"` / `"outer"` | Стиль glow: `inner` — свечение внутрь (shrink→edge→blur→composite), `outer` — свечение наружу (классический). В UI — сегментный контрол (ParamToggle) |
| `stone_gamma` | float | 0.88 | 0.5–1.5 | Поправочная гамма для камня (заменяет `brightness`). < 1.0 осветляет тени, > 1.0 затемняет |
| `face_brightness_target_min` | int | 230 | 80–255 | Минимальная целевая яркость лица. Если текущая ниже — применяется автокоррекция |
| `face_brightness_target_max` | int | 245 | 80–255 | Максимальная целевая яркость лица. Если текущая выше — коррекция не применяется |
| `white_ceiling` | int | 250 | 200–255 | Потолок белой точки. Ни одного пикселя (кроме зрачков) не может быть ярче. Предотвращает пережжённые блики на камне |
| `rolloff_compression` | float | 0.35 | 0.1–0.8 | Степень сжатия highlights в soft rolloff. 0.35 = мягкий (сохраняет текстуру), 0.50 = средний, 0.80 = жёсткий (ближе к hard clip). Gates могут увеличивать при clipped_pct > 5% |

### Особенности laser standard

- Широкий мягкий glow (40–80px, 30–40%) — создаёт плавный контур, хорошо видно на камне
- Glow детерминирован (D.1): midpoint диапазона вместо random — preview и export идентичны
- Лицо светлое (230–245) — лазер «выжигает» светлые участки, тёмные остаются камнем
- Fringe radius 3 обязателен — синие рефлексы на волосах при вырезке
- White ceiling 250 — только зрачки могут быть чисто белыми
- Формат экспорта по умолчанию: **BMP 8-bit grayscale**

> **Совместимость:** Старый формат `face_brightness_target: [230, 245]` (список) автоматически конвертируется в отдельные ключи `_min`/`_max` при загрузке.

---

## processing.laser_80w

Параметры для мощных лазеров 60–80W+ (Mirtels, Stanzone).

| Параметр | Тип | Default | Диапазон | Описание |
|----------|-----|---------|----------|----------|
| `glow_size_min` | int | 15 | 5–100 | Минимальный размер Glow (px) |
| `glow_size_max` | int | 25 | 5–100 | Максимальный размер Glow (px) |
| `glow_opacity_min` | int | 10 | 10–100 | Минимальная opacity Glow (%) |
| `glow_opacity_max` | int | 20 | 10–100 | Максимальная opacity Glow (%) |
| `glow_style` | toggle | `"outer"` | `"inner"` / `"outer"` | Стиль glow |
| `stone_gamma` | float | 1.0 | 0.5–1.5 | Поправочная гамма для камня. При export_mode='8bit' Engrave сам управляет яркостью |
| `face_brightness_target_min` | int | 160 | 80–255 | Минимальная целевая яркость лица (перекалибровка для gamma=1.0) |
| `face_brightness_target_max` | int | 180 | 80–255 | Максимальная целевая яркость лица |
| `export_mode` | toggle | `"8bit"` | `"8bit"` / `"1bit"` | Режим экспорта BMP. 8bit=grayscale (Engrave растрирует сам), 1bit=дизеринг |
| `step_mm` | float | 0.250 | 0.10–0.50 | Шаг ЧПУ (мм). Для лазера: 0.125–0.250 (по мануалу САУНО) |
| `dither_method_1bit` | toggle | `"jarvis"` | `"jarvis"` / `"stucki"` | Метод дизеринга при export_mode='1bit' |
| `white_ceiling` | int | 235 | 200–255 | Потолок белой точки (строже для мощного лазера — пережог критичнее) |

### Особенности laser 80W

- Минимальный glow (15–25px, 10–20%) — мощный лазер сам создаёт контраст, усиление не нужно
- Лицо пониженной яркости (160–180) — при gamma=1.0 и 8-bit Engrave сам управляет яркостью через Р-графики
- Тёмные волосы с мягкими бликами — при мощном лазере яркие блики пережигаются
- Морщины сохраняются как мягкие тональные переходы — в отличие от laser_standard (абсолютная гладь)
- Формат экспорта по умолчанию: **BMP 8-bit grayscale** — Engrave модулирует мощность лазера по яркости (алгоритмы Р1–Р5)
- Переключение на 1-bit: export_mode='1bit' + dither_method_1bit='jarvis' — для станков без Engrave
- **Предпросмотр дизеринга** — кнопка «Просмотр дизеринга» в StepSelector для всех машин. Без Numba — 30-120 сек с подтверждением

---

## processing.impact

Параметры для ударной гравировки (Sauno, Zubr, Mirtels).

| Параметр | Тип | Default | Диапазон | Описание |
|----------|-----|---------|----------|----------|
| `glow_size_min` | int | 10 | 5–100 | Минимальный размер Glow (px) |
| `glow_size_max` | int | 25 | 5–100 | Максимальный размер Glow (px) |
| `glow_opacity_min` | int | 60 | 10–100 | Минимальная opacity Glow (%) |
| `glow_opacity_max` | int | 80 | 10–100 | Максимальная opacity Glow (%) |
| `glow_style` | toggle | `"inner"` | `"inner"` / `"outer"` | Стиль glow |
| `stone_gamma` | float | 0.88 | 0.5–1.5 | Поправочная гамма для камня |
| `face_brightness_target_min` | int | 170 | 80–255 | Минимальная целевая яркость лица. Для impact ниже чем для laser_standard |
| `face_brightness_target_max` | int | 215 | 80–255 | Максимальная целевая яркость лица. Пересвет критичен для иглы |
| `white_ceiling` | int | 245 | 200–255 | Потолок белой точки |
| `shadow_noise_min` | int | 5 | 0–50 | Минимальный шум в глубоких тенях. 0 = без шума |
| `shadow_noise_max` | int | 15 | 0–50 | Максимальный шум в глубоких тенях. 0 = без шума |
| `shadow_floor` | int | 2 | 0–30 | Минимальная яркость в тенях субъекта. Impact: предотвращает застой иглы на чёрном |
| `shadow_noise_threshold` | int | 30 | 5–80 | Порог яркости для shadow noise: шум добавляется только в пиксели < threshold |

### Особенности impact

- Узкий яркий glow (10–25px, 60–80%) — чёткий контур, игла хорошо считывает границу
- Лицо умеренной яркости (170–215) — пересвет критичнее чем для лазера, игла не различает оттенки выше 240
- Shadow noise (5–15) — игла impact-станка не бьёт в полностью чёрные пиксели (нет точек), шум даёт игле «зацепку». Шум добавляется только внутри маски субъекта в пикселях с яркостью < shadow_noise_threshold
- Shadow floor (2) — минимальная яркость в тенях, предотвращает застой иглы на чистом чёрном
- Формат экспорта по умолчанию: **BMP 8-bit grayscale**

---

## machine

Глобальные параметры станка. Начиная с v3, `step_mm` задаётся **per-machine** в секции `processing.{machine}.step_mm`. Глобальный `machine.step_mm` сохранён как fallback (обратная совместимость).

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `step_mm` | float | 0.300 | Шаг гравировки (мм), fallback если не задан per-machine |

---

## stone

Профиль камня для адаптации обработки.

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `type` | string | `granite` | Тип камня: `granite`, `marble`, `gabbro`, `basalt` — профиль камня |
| `heterogeneity` | float | null | Неоднородность камня. null = auto по stone_type (будущее) |

---

## gimp

Настройки поиска GIMP (для команды `retouch gimp`).

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `search_paths` | [string] | `["F:\\GIMP 2\\bin\\...", "C:\\Program Files\\..."]` | Список путей к gimp-console. Первый найденный используется |
| `env_var` | string | `GIMP_PATH` | Переменная окружения для переопределения пути к GIMP |

Приоритет: `env_var` > `search_paths[0]` > `search_paths[1]` > ...

---

## vignette

Параметры арховой виньетки. Все значения — доли от размера изображения, виньетка масштабируется автоматически.

| Параметр | Тип | Default | Диапазон | Описание |
|----------|-----|---------|----------|----------|
| `vertical_offset` | float | 0.10 | 0.0–0.3 | Отступ нижнего края арки от низа изображения (доля высоты). Больше → больше чёрного внизу |
| `vertical_diameter` | float | 0.50 | 0.2–0.8 | Высота эллипса арки (доля высоты). Больше → арка выше и шире |
| `blur_radius` | int | 60 | 10–120 | Размытие края виньетки (px). Больше → плавнее переход |
| `headroom` | float | 0.6 | 0.2–1.0 | Запас над головой (доля высоты). Больше → голова дальше от края арки |
| `horizontal_oversize` | float | 0.2 | 0.0–0.5 | Расширение эллипса за пределы изображения (доля ширины). Больше → шире по бокам |

### Формулы

Для изображения `W × H`:

```
arch_bottom_y = H - (H × vertical_offset)
arch_top_y    = arch_bottom_y - (H × vertical_diameter) - (H × headroom)
ellipse_left  = -(W × horizontal_oversize)
ellipse_right = W + (W × horizontal_oversize)
```

### Пресеты

| Название | vertical_offset | vertical_diameter | blur_radius | headroom | horizontal_oversize |
|----------|:-:|:-:|:-:|:-:|:-:|
| Стандартный | 0.10 | 0.50 | 60 | 0.6 | 0.2 |
| Широкая арка (погоны) | 0.08 | 0.65 | 60 | 0.6 | 0.3 |
| Узкая арка (медальон) | 0.15 | 0.40 | 50 | 0.7 | 0.1 |
| `impact-default.yaml` | 0.10 | 0.50 | 80 | 0.6 | 0.2 |

---

## Пресеты (Presets)

Пресеты находятся в директории `presets/` и представляют собой готовые наборы параметров для конкретных типов станков. Каждый пресет явно дублирует критические параметры для обеспечения предсказуемости результата.

| Пресет | Описание | Основные параметры |
|--------|----------|--------------------|
| `laser-default` | Канонический для `laser_standard` | target: 230–245, ceiling: 250, gamma: 0.88, export_mode: 8bit |
| `laser-80w-default` | Канонический для `laser_80w` | target: 160–180, ceiling: 235, gamma: 1.0, export_mode: 8bit |
| `impact-default` | Канонический для `impact` | target: 200–225, ceiling: 240, gamma: 0.90, export_mode: 8bit |

> [!NOTE]
> Ключ `brightness` объявлен **deprecated** и автоматически мигрирует в `stone_gamma = 1 / brightness`. Используйте `stone_gamma` в новых пресетах.

---

См. подробнее: [guides/vignette.md](../guides/vignette.md).

---

## crm

Настройки связи с granite-crm.

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `crm_path` | string | `""` | Путь к репозиторию granite-crm (для доступа к данным) |
| `env_var` | string | `GRANITE_CRM_PATH` | Переменная окружения для переопределения пути |

Приоритет: `env_var` > `crm_path`.

См. подробнее: [integration/crm.md](../integration/crm.md).

---

## Адаптивный pipeline

Pipeline автоматически выполняет преданализ изображения после конвертации в grayscale. Модуль `retouch/processing/analysis.py` измеряет 13 метрик внутри маски субъекта и передаёт результат в последующие шаги (Glow, Levels, Unsharp). Это позволяет адаптировать параметры обработки под конкретное входное изображение вместо использования фиксированных значений.

Если analytics недоступен (numpy не установлен) — используется legacy mode с фиксированными параметрами из конфига.

Ключевые адаптивные механизмы:
- **Levels**: фактор яркости вычисляется из `median_brightness` вместо фиксированного множителя
- **Glow**: параметры зависят от `subject_separation` и `tonal_range`, детерминированы через midpoint (D.1)
- **Unsharp**: percent зависит от `input_class` и `tonal_range`
- **Face Detection (C.1)**: трёхуровневая стратегия (профиль ширины маски → ручной овал → mediapipe в будущем)
- **Glow детерминированность (D.1)**: midpoint вместо random, preview-export consistency
- **Quality Metrics (F.2)**: `clipped_pixels_pct`, `shadow_crush_pct`, `tonal_range_output`, `quality_warnings`
- **BMP Post-Validation (F.3)**: автоматическая проверка mode и size после сохранения
- **ZoneMasks (v6.4)**: автоматическое зональное разделение — коррекция только к нужным зонам
- **Step metrics**: метрики по зонам после каждого шага — видно какой шаг ухудшил результат
- **Quality gates**: 7 контрольных точек — автоматическое ослабление агрессивных шагов

---

## processing profiles (v6.4)

Профиль обработки задаёт множество активных шагов и ограничения на агрессивность:

| Профиль | Активные шаги | Описание |
|---------|--------------|----------|
| `standard` | все | Полная обработка (по умолчанию) |
| `preserve` | chromakey, grayscale, glow, rolloff, vignette | Минимальное вмешательство — без levels, face_correction, unsharp |
| `diagnostic` | все + расширенный сбор масок | Для отладки — сохраняет все промежуточные маски и метрики |

Профиль и пресет ортогональны: `preserve + laser_80w` = параметры `laser_80w`, но безопасный набор шагов.

---

## safety_envelope (v6.4)

Максимальная допустимая дельта коррекции по зонам:

| Параметр | Default | Описание |
|----------|---------|----------|
| `face_skin_max_delta` | 15.0 | Максимальная коррекция кожи лица (±15 уровней ≈ 6%) |
| `face_dark_max_delta` | 5.0 | Максимальная коррекция тёмных участков лица |
| `hair_max_delta` | 3.0 | Максимальная коррекция волос |
| `clothes_max_delta` | 0.0 | Одежда не корректируется по решению лица |
| `highlights_rolloff_only` | true | Highlights — только rolloff, без подъёма |
| `contour_inner_glow_only` | true | Внутренний контур — только glow/edge logic |
| `contour_outer_antifringe_only` | true | Внешний контур — только антифринги |

Пример в config.yaml:
```yaml
safety_envelope:
  face_skin_max_delta: 20.0  # увеличить для тёмных портретов
  hair_max_delta: 5.0        # разрешить лёгкую коррекцию волос
```

---

## export

По умолчанию пайплайн экспортирует **BMP** — стандартный формат для ЧПУ станков. Начиная с v3, формат определяется по `export_mode` из per-machine конфига:

| Machine type | export_mode | Формат по умолчанию | Описание |
|---|---|---|---|
| `laser_standard` | `8bit` | BMP 8-bit grayscale | 256 оттенков, палитра R=G=B. Engrave растрирует алгоритмами Р1–Р5 |
| `laser_80w` | `8bit` | BMP 8-bit grayscale | Engrave модулирует мощность лазера по яркости пикселей |
| `impact` | `8bit` | BMP 8-bit grayscale | 256 уровней силы удара ударного станка |
| любая | `1bit` | BMP 1-bit (dithered) | Монохромный с Jarvis/Stucki дизерингом — для станков без Engrave |

DPI в заголовке BMP вычисляется из `step_mm`: `dpi = 25.4 / step_mm`. Engrave НЕ использует DPI из заголовка, но предупреждает при несоответствии.

Дополнительно сохраняется PNG для визуальной проверки (при `save_png_preview=True`).

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `--format` | string | `bmp` | Формат экспорта CLI: `bmp`, `bmp_1bit`, `bmp_8bit`, `png`, `tiff` |
| `--overwrite` | flag | — | Перезаписать выходной файл без подтверждения. Без флага — exit(1) если файл существует (D.7) |

Форматы:
- `bmp` — автоматический выбор по export_mode из конфига (по умолчанию 8-bit для всех машин)
- `bmp_8bit` — принудительно 8-bit grayscale BMP
- `bmp_1bit` — принудительно 1-bit монохромный BMP с Jarvis/Stucki дизерингом
- `png` — PNG (для предпросмотра / совместимости)
- `tiff` — TIFF с LZW-сжатием (legacy, для совместимости со старыми станками)

**Миграция v2→v3:** `dither_method=jarvis` → `export_mode=1bit, dither_method_1bit=jarvis`. `dither_method=none` → `export_mode=8bit`. Миграция идемпотентна.
