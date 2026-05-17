# FIX: Pixel Report — попиксельный анализ портрета

## Рабочий процесс

Ты кидаешь фото в `orders/active/ORD-XXXX-XXX/generated/source.jpg`.
Я запускаю пайплайн, сохраняю артефакты + анализ в ту же папку.
Ты смотришь отчёт и решаешь, что крутить.

### Структура заказа после анализа

```
orders/active/ORD-2026-XXX/
├── order.json
├── prompt.md
└── generated/
    ├── source.jpg            ← исходное фото (ты кинул)
    ├── ai.png                ← нейро-ретушь (опционально)
    ├── face_mask.png         ← маска лица (debug artifact)
    ├── subject_mask.png      ← маска субъекта (debug artifact)
    ├── final.bmp             ← результат пайплайна
    ├── pixel-report.json     ← числовой отчёт
    ├── pixel-report.txt      ← человекочитаемый отчёт
    └── heatmap.png           ← визуализация проблем
```

### Что я делаю

1. Ты говоришь: «ORD-2026-XXX, impact, проанализируй»
2. Я запускаю `process` с `--debug-dir`
3. Запускаю `pixel_report()` на результате
4. Сохраняю JSON + TXT + heatmap в `generated/`
5. Отвечаю: «15% лица — плато на 240, variance loss 29%»

## Мотивация

Текущая итерация (v6: soft knee) не проверена — пользователь не может
увидеть, что именно происходит с пикселями на лице. Нужен инструмент,
который:

1. Сохраняет промежуточные артефакты пайплайна (face_mask, subject_mask,
   результат до/после каждого шага)
2. Анализирует результат: плато, потеря текстуры, ceiling clip,
   границы маски
3. Даёт структурированный отчёт для принятия решений о настройках

Без авто-подстройки — только диагностика для человека.

## Диагностика: ORD-2026-007 (анализ исходника ai.png)

### Что на фото

Женщина, короткая волнистая стрижка. Чёрная блузка (нижняя половина,
очень тёмная). Белый кружевной воротник (детализированный, яркий).
Лицо нормальная экспозиция. Синий хромакей.

### Анализ яркости (по зонам)

| Зона | Медиана | p90 | p95 | max |
|------|:---:|:---:|:---:|:---:|
| Всё изображение | 28 | 235 | 246 | 255 |
| Субъект (без фона) | 12 | 202 | 215 | 230 |
| **Лицо** (верх 45% субъекта) | **121** | **211** | **218** | **227** |
| Остальной субъект | 8 | 190 | — | 230 |

### Распределение субъекта

| Зона | % пикселей |
|------|:---:|
| Тёмные (<50) — чёрная одежда | 59.7% |
| Средние (50-150) | 16.7% |
| Яркие (150-220) — лицо, воротник | 20.7% |
| Горячие (>=220) | 2.9% |

### Что делает пайплайн (и почему ломает)

```
Медиана субъекта = 12 (чёрная одежда тянет вниз)
target_pre_fb = 160
Фактор = 160 / 12 = 13.33 (безумие)
Защита по p90 снижает до ~1.18, но:
  p90 лица 211 → 279 (клип к 250)
  p95 лица 218 → 288 (клип к 250)
  22.6% лица улетает в ceiling=250
```

### Корень проблемы

**`analyze_input()` считает медиану по subject_mask, а не по face_mask.**
Subject mask включает чёрную одежду → медиана 12 → levels думает
«фото тёмное, надо осветлить в 13 раз» → лицо и воротник сгорают.

Лицо уже на 121 — оно НЕ тёмное. Пайплайн чинит то, что не сломано.

### Решение (раз и навсегда, не под каждое фото)

1. **Levels factor считать по лицу, не по всему субъекту**
   - Если лицо уже > 100 → factor ≈ 1.0 (не трогать)
   - Если лицо < 80 → осветлять до target_pre_fb
2. **Снизить target_pre_fb с 150/160 до 130**
   - Лицо на 121 → factor = 130/121 = 1.07 (лёгкая коррекция)
   - p90 = 211 × 1.07 = 226 (не упирается в ceiling)
3. **Защиту по p95, а не по p90**
   - p90 не ловит горячие пиксели на лбу (p95=218, p98=223)

### Почему овал лица не виноват

Овал накладывается ПОСЛЕ levels. К моменту face correction лицо
уже сожжено levels (211 → 279 → клип 250). Овал не может
восстановить потерянную текстуру.

### Почему воротник тоже страдает

Белый кружевной воротник: p90=190. После factor 1.32 → 250 (клип).
Детали кружева теряются. Решение то же — не задирать levels.

---

## Архитектура

### Новый пакет: `retouch/debug/`

```
retouch/debug/
├── __init__.py
├── pixel_report.py     # Основной модуль: метрики, отчёт, heatmap
```

### CLI: `retouch debug report`

```bash
python -m retouch debug report \
    -i source.png \
    -o output.bmp \
    -m impact \
    --face-mask face_mask.png \
    --subject-mask subject_mask.png \
    --debug-dir debug/ \
    --heatmap heatmap.png \
    --json report.json
```

### Вывод: JSON + терминал + опциональный heatmap

---

## Метрики

### 1. Plateaus (плоские области)

**Что:** contiguous run'ы пикселей с value в tolerance=2,
сканируем строку за строкой.

**Как:**
```python
def analyze_plateaus(arr: np.ndarray, mask: np.ndarray,
                     tolerance: int = 2) -> dict:
    """
    arr: uint8 (H×W)
    mask: bool (H×W)
    
    Returns:
      pct_face:   % face pixels in plateaus
      pct_subject:% subject pixels in plateaus
      max_area:   largest plateau size (px)
      peak_value: most common plateau value
      per_value:  {value: pct} — распределение плато по значениям
    """
```

**Находит:** пиксели, которые склеились в одинаковые значения.
Сканируем строки: если подряд N >= 5 пикселей с deviation <= 2 —
это плато. 5px minimum, чтобы не ловить естественные гладкие области
(щёки).

### 2. Ceiling Clip

**Что:** % пикселей, упёршихся в white_ceiling.

```python
def analyze_ceiling_clip(arr: np.ndarray, ceiling: int,
                         mask: np.ndarray) -> dict:
    """
    Returns:
      at_ceiling_pct: % mask pixels == ceiling
      above_245_pct:  % mask pixels >= 245 (near-ceiling hot)
      max_value:      brightest pixel value
    """
```

### 3. Detail Loss (сравнение с исходником)

**Что:** насколько упала локальная variance после пайплайна.

```python
def analyze_detail_loss(before: np.ndarray, after: np.ndarray,
                        mask: np.ndarray) -> dict:
    """
    before: uint8 (H×W) — исходник (grayscale)
    after:  uint8 (H×W) — результат пайплайна
    
    Returns:
      var_before:    mask variance before
      var_after:     mask variance after
      var_loss_pct:  (before - after) / before * 100
      edge_before:   mean sobel magnitude before
      edge_after:    mean sobel magnitude after
      edge_loss_pct: (edge_before - edge_after) / edge_before * 100
      local_var_loss: heatmap (H×W float 0-1) — отношение after/before
                       per 5×5 tile
    """
```

**Зачем:** если variance упала на > 30% — текстура лица съедена.
Если упала на > 50% — плато.

### 4. Brightness Shift

**Что:** как изменилось распределение яркости на лице.

```python
def analyze_brightness_shift(before: np.ndarray, after: np.ndarray,
                              mask: np.ndarray) -> dict:
    """
    Returns:
      mean_before, mean_after, mean_shift
      p90_before,  p90_after,  p90_shift
      p95_before,  p95_after,  p95_shift
      # Новые поля, которых нет в analysis.py:
      p98_before,  p98_after,  p98_shift
    """
```

**Зачем:** p90 shift показывает, насколько levels поднял горячие пиксели.
Если p90 упёрся в ceiling — levels factor пережат.

### 5. Mask Boundary Artifacts

**Что:** видимый стык на границе face_mask.

```python
def analyze_boundary(arr: np.ndarray, face_mask: np.ndarray) -> dict:
    """
    arr:       uint8 (H×W) — результат
    face_mask: bool (H×W)
    
    Дilate face_mask на 3px → annulus (кольцо).
    Сравниваем mean внутри annulus vs outside annulus.
    
    Returns:
      boundary_gradient: max(mean_inside - mean_outside)
      gradient_map:  (H×W float) — разница blurred inside vs outside
      boundary_detected: bool (gradient > 10)
    """
```

### 6. Input Quality (предварительный анализ исходника)

**Что:** быстрый срез исходника без прогона пайплайна.

```python
def analyze_input_quality(source_path: str, face_mask_path: str = None) -> dict:
    """
    Загружает source, анализирует яркость, контраст.
    Полезно знать ДО запуска пайплайна.
    """
```

---

## Pipeline: сохранение промежуточных артефактов

Чтобы pixel report работал, пайплайн должен сохранять:

| Файл | Откуда в pipeline | Когда |
|------|-------------------|-------|
| `face_mask.png` | `ctx.face_mask` | после face_region |
| `subject_mask.png` | `ctx.subject_mask` | после chromakey |
| `before_levels.png` | до `apply_levels` | опционально |
| `after_levels.png` | после `apply_levels` | опционально |
| `after_unsharp.png` | после unsharp | опционально |

Проще всего: **опция `--debug-dir`** в `retouch process`. Если передана,
пайплайн сохраняет маски и промежуточные результаты.

**Изменение: `retouch/processing/pipeline.py`**

```python
def process(input_path, output_path, machine_type, ...,
            debug_dir: str | None = None): ...

def _run_pipeline_steps(ctx, ...):
    if ctx.debug_dir:
        ctx.face_mask.save(f"{ctx.debug_dir}/face_mask.png")
        ctx.subject_mask.save(f"{ctx.debug_dir}/subject_mask.png")
    # ... после каждого шага:
    if ctx.debug_dir:
        Image.fromarray(arr.astype(np.uint8)).save(f"{ctx.debug_dir}/step_04_levels.png")
```

---

## Heatmap

**Файл:** `retouch/debug/heatmap.py` (или внутри pixel_report.py)

RGB overlay (на белую подложку или на полупрозрачный слой):

| Цвет | Условие | Значение |
|------|---------|----------|
| 🔴 Красный | plateau (в плато) | clip loss > 50% |
| 🟡 Жёлтый | variance loss > 30% | детали съедены |
| 🟢 Зелёный | variance loss < 10% | норма |
| ⚫ Чёрный | вне subject_mask | фон |

```python
def generate_heatmap(width: int, height: int,
                     mask: np.ndarray,
                     plateau_map: np.ndarray,
                     var_loss_map: np.ndarray) -> Image.Image:
    """
    Returns RGB Image (H×W×3).
    """
```

---

## Сводный отчёт

### Терминал (print)

```
=== PIXEL REPORT: impact / output.bmp ===

INPUT:
  Face median: 135 | class: dark
  Face p90:    200 | p95: 218

OUTPUT:
  Face median: 162 | class: medium
  Face p90:    235 | p95: 240

CEILING (240):
  Face at ceiling:      15.2%  ← плоское плато
  Subject at ceiling:    8.3%
  Pure white (255):      0.0% ✓

PLATEAUS:
  Face in plateaus:         12.5% (max area 450px, peak at 240)
  Subject in plateaus:       7.1%
  ↑ Ударный: 15% лица — плоское серое плато на 240

DETAIL LOSS (vs source):
  Face variance:  120.5 → 85.3  (↓29%)
  Edge density:    0.15 → 0.09  (↓40%)
  ↑ Текстура лица съедена на 29-40%

MASK BOUNDARY:
  Boundary gradient: 12.3  ← заметен глазом (> 10)
  Boundary detected: yes

RECOMMENDATIONS:
  ▶ Добавить soft knee: 15% face at ceiling
  ▶ Снизить levels factor: p90 shift +35 тянет к ceiling
  ▶ Проверить boundary feathering: gradient 12 на границе маски
```

### JSON (`--json report.json`)

```json
{
  "meta": {
    "source": "source.png",
    "output": "output.bmp",
    "machine": "impact",
    "ceiling": 240,
    "face_target_max": 225
  },
  "input": {
    "face_median": 135,
    "face_p90": 200,
    "face_p95": 218,
    "class": "dark"
  },
  "output": {
    "face_median": 162,
    "face_p90": 235,
    "face_p95": 240
  },
  "ceiling_clip": {
    "face_at_ceiling_pct": 15.2,
    "subject_at_ceiling_pct": 8.3,
    "pure_white_pct": 0.0
  },
  "plateaus": {
    "face_pct": 12.5,
    "subject_pct": 7.1,
    "max_area": 450,
    "peak_value": 240,
    "per_value": {"240": 8.2, "239": 2.1, "238": 1.1}
  },
  "detail_loss": {
    "face_variance_before": 120.5,
    "face_variance_after": 85.3,
    "variance_loss_pct": 29.2,
    "face_edge_density_before": 0.15,
    "face_edge_density_after": 0.09,
    "edge_loss_pct": 40.0
  },
  "mask_boundary": {
    "gradient_max": 12.3,
    "detected": true
  },
  "recommendations": [
    "15.2% face at ceiling=240 — добавить soft knee или снизить levels factor",
    "variance loss 29% — текстура лица съедена"
  ]
}
```

---

## Файлы

| Файл | Действие |
|------|----------|
| `retouch/debug/__init__.py` | создать (пустой) |
| `retouch/debug/pixel_report.py` | создать (~250 строк) |
| `retouch/debug/heatmap.py` | создать (~80 строк, heatmap overlay) |
| `retouch/cli.py` | добавить `debug report` subparser + `cmd_debug_report()` |
| `retouch/processing/pipeline.py` | добавить `--debug-dir` сохранение промежуточных артефактов |
| `tests/test_pixel_report.py` | создать (~150 строк, синтетические тесты) |
| `docs/reference/cli.md` | обновить: добавить `debug report` |
| `FIX-overexposure-plan.md` | обновить: ссылка на pixel report |

---

## Срок

1 день разработки:
- `retouch/debug/` — 4-5 часов
- `pipeline.py` debug-dir — 1 час
- CLI — 1 час
- Тесты — 2 часа
- Документация — 30 мин

После запуска (завтра) — приоритет ниже production.

---

*Создано: 2026-05-17*
