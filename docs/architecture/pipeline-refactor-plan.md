# План рефакторинга пайплайна обработки

Документ фиксирует текущие проблемы пайплайна и план рефакторинга от
критичных исправлений перед продом до полной zonal-логики.

## Контекст

Текущий пайплайн решает задачу слишком глобально: он измеряет яркость лица,
но затем применяет часть коррекций ко всему субъекту. Для экспресс-ретуши это
опасно: оператор ожидает, что система слегка подготовит уже готовую AI-ретушь
к станку, а не заново перетонит портрет.

Цель рефакторинга: перейти от глобального изменения портрета к минимальному
вмешательству в доказанно проблемные зоны.

## Основные проблемы

### Глобальные коррекции по локальной метрике

`analyze_input()` может считать `median_brightness`, `p90`, `p95` по лицу, но
`apply_levels()` применяет рассчитанный factor ко всей `subject_mask`.

Итог:

- кожа задаёт коэффициент;
- волосы, одежда и контур меняются вместе с кожей;
- чёрная одежда и волосы теряют естественную плотность;
- светлые зоны могут уходить в ceiling и терять фактуру.

### Слишком много тональных этапов подряд

Текущая цепочка:

```text
chromakey -> grayscale -> glow -> levels -> face correction -> unsharp
-> shadow noise -> shadow floor -> stone gamma -> white ceiling -> vignette
```

Каждый шаг выглядит оправданным отдельно, но в сумме они образуют каскад:
сначала изображение поднимается, затем сжимается, затем шарпится, затем снова
ограничивается. Это ухудшает сохранность исходной ретуши.

### Ceiling применяется в нескольких местах

Ограничение яркости есть в `levels`, `unsharp` и финальном postprocess.
Это создаёт риск плато в светах: разные значения становятся одинаковыми, и
исчезает текстура кожи, лба, воротника и бликов.

### Soft knee в postprocess сейчас не работает

В `pipeline.py` используется chained boolean indexing:

```python
arr[mask_bool][over] = knee + excess * 0.35
```

Такой код пишет во временную копию, а не в `arr`. В результате soft knee
фактически не применяется, остаётся обычный hard clip.

Важно: это локальный баг финального postprocess. В `levels.py` soft knee
реализован через прямую индексацию полного массива `corrected[over]` и работает
иначе. Его не нужно "чинить" тем же способом.

Дополнительная проблема: в разных местах используются разные коэффициенты
сжатия светов. В `levels.py` сохраняется 50% excess выше knee, а в
`pipeline.py` задумано 35%. Это должно стать явным параметром, а не
хардкодом в двух модулях.

### Face brightness больше не соответствует названию target range

`check_face_brightness()` сейчас только затемняет лицо и никогда не осветляет.
При этом в конфиге остаются `face_brightness_target_min` и
`face_brightness_target_max`.

Если нижняя граница не используется для коррекции, она должна быть либо
диагностической метрикой, либо логика должна снова поддерживать мягкое
осветление.

### Shadow floor применяется шире, чем кажется

`shadow_floor` задан не только для impact, но и для laser-конфигов. Если floor
применяется ко всей маске субъекта, он может поднимать настоящие глубокие тени
в волосах, одежде и деталях лица.

### Диагностика не управляет пайплайном

Метрики качества считаются после всех шагов. Они показывают, что результат
плохой, но не предотвращают деградацию и не откатывают агрессивный шаг.

Post-hoc rollback сложен: ослабление одного шага меняет вход следующего шага.
Поэтому лучше двигаться к pre-check модели: сначала построить `PipelinePlan`,
проверить ожидаемый риск, затем применить уже безопасные параметры.

## Принцип нового пайплайна

Экспресс-режим не должен требовать ручной разметки всех зон.

Ручным остаётся максимум один объект: овал лица. Он уже есть в проекте и может
быть поправлен оператором в UI.

Остальные зоны вычисляются автоматически:

```text
face_skin  = face_mask & subject_mask & gray >= skin_threshold
face_dark  = face_mask & subject_mask & gray < skin_threshold
hair       = hair_mask
clothes    = subject_mask & ~face_mask & ~hair_mask
highlights = subject_mask & gray >= highlight_threshold
contour_inner = contour_inner_from_chromakey_gradient
contour_outer = contour_outer_from_chromakey_gradient
background = ~subject_mask
```

Это не полноценная семантическая сегментация. Это рабочие технические зоны,
достаточные для того, чтобы не применять одну коррекцию ко всему портрету.

`skin_threshold` не должен оставаться только абсолютным значением `100`.
Для тёмной кожи, бороды, усов и контрового света нужен адаптивный порог от
распределения яркости внутри `face_mask`, например `median(face) - delta`.

Контур лучше строить не грубым `dilate - erode`, а из существующей
градиентной маски хромакея или её края. Нужны две разные зоны:

- `contour_inner` — внутренний край субъекта для glow и сохранения плотности;
- `contour_outer` — внешний переход в фон для антифринги.

Если использовать одну общую contour-маску, легко смешать задачи glow и
антифринги и потерять аккуратную работу `chromakey.py` по мягкому краю.

Черновая бинарная формула:

```python
gradient = chromakey_gradient_mask  # float 0..1
contour_inner = (gradient > 0.5) & (gradient < 1.0)
contour_outer = (gradient > 0.0) & (gradient <= 0.5)
```

Порог `0.5` должен быть параметром. Если нужен мягкий край, вместо bool-масок
можно хранить float-веса, но primary zoning ниже остаётся дизъюнктным.

**Fallback для некачественного gradient:** если `contour_inner` занимает >30%
от `subject_mask`, gradient mask некачественная (хромакей с пропусками или
неровным краем). В этом случае — fallback на morphological contour
(`dilate(subject_mask) - erode(subject_mask)`) с diagnostics warning
`contour_fallback_used`.

Все зональные операции должны проектироваться как batch numpy pass: одна
конверсия PIL -> numpy, несколько масок и операций в массиве, одна конверсия
обратно. Это критично для больших изображений вплоть до 8K.

### Memory budget для 8K

ZoneMasks на 8K (7680×4320) — это 9 uint8-масок + grayscale + оригинал.
Каждая маска uint8: ~33 MB. Девять масок: ~300 MB. С оригиналом, grayscale и
рабочими массивами процесс может превысить 1 GB.

Ограничения:
- маски хранятся как `uint8` (bool через `astype` только в момент операции);
- одновременно в памяти не больше трёх полных масок + grayscale + arr;
- после `resolve_zone_priority()` ненужные исходные маски удаляются (`del`);
- для preview (максимум 1920px по длинной стороне) budget не должен превышать
  128 MB на маски;
- если `subject_mask` меньше 30% кадра, partial masks хранятся в ROI-cжатом
  виде через bbox исходной маски.

Порядок построения: subject + face + gray → hair → contour → highlights
→ clothes → resolve_zone_priority() → del исходные маски. Это гарантирует,
что одновременно в памяти не более трёх полных масок.

Проверять в тестах: `test_zone_masks_memory_8k` — создаёт маски номинального
размера, проверяет, что пиковое выделение не превышает лимит. Лимит выставляется
явно (например, 800 MB для 8K single-pass), чтобы CI ловил регресс.

### Time budget

- **Preview**: < 1s при разрешении до 1920px по длинной стороне;
- **Export**: < 5s при разрешении до 8K (7680×4320);
- Пороги — параметры конфига с указанными дефолтами, чтобы CI ловил регресс;
- Тест `test_pipeline_performance` запускает полный пайплайн на fixture-изображении
  номинального размера и проверяет, что общее время не превышает лимит.

Пересечения зон должны разрешаться до применения операций. Базовая политика:
`highlights > face_skin > face_dark > hair > clothes > contour`. Пиксель
получает одну основную коррекцию по самой приоритетной зоне. Финальный
highlight rolloff допускается как общий ограничитель, но его параметры должны
учитывать уже запланированную коррекцию кожи в `PipelinePlan`.

Контракт `resolve_zone_priority()` — дизъюнктное разбиение, не weighted blend:

```python
final_highlights = highlights
final_face_skin = face_skin & ~final_highlights
final_face_dark = face_dark & ~final_highlights & ~final_face_skin
final_hair = hair & ~final_highlights & ~final_face_skin & ~final_face_dark
final_clothes = clothes & ~final_highlights & ~final_face_skin & ~final_face_dark & ~final_hair
final_contour_inner = contour_inner & ~final_highlights & ~final_face_skin
final_contour_inner &= ~final_face_dark & ~final_hair & ~final_clothes
final_contour_outer = contour_outer  # outside subject_mask, no priority conflict
```

Все `final_*` маски не пересекаются. Это упрощает batch pass, тесты и
объяснение результата оператору.
`contour_outer` не участвует в основной subject-zone приоритизации, потому что
лежит вне `subject_mask`.

`background` исключён из priority resolution и не получает тональных
коррекций — это зона фона (хромакей), которая остаётся без изменений.

### Edge case: борода и усы

В приоритете `face_skin > face_dark > hair` борода и усы попадают в
`face_skin` (если пиксели ярче порога) или `face_dark` (если темнее).
Это может быть нежелательно: оператор ожидает, что борода — это hair-зона.

Явное правило:

- если `face_dark` составляет >40% от `face_mask`, подозреваем бороду/усы —
  пиксели ниже `face_dark` в нижней трети овала лица переклассифицируются в
  `hair`;
- spatial check: >60% пикселей `face_dark` должны быть сконцентрированы
  в нижней трети овала. При равномерном распределении (тёмная кожа без
  бороды) `face_dark > 40%` не считается бородой — это отсекает ложные
  срабатывания на тёмной коже;
- порог переклассификации и доля `face_dark` — параметры конфига с разумными
  значениями по умолчанию (0.40, 0.60, нижняя треть);
- переклассификация применяется только если `hair_mask` уже есть и не пуста
  (иначе нет уверенности, что hair-зона вообще определена);
- diagnostics показывает флаг `beard_suspected` и количество переброшенных
  пикселей.

Это не обязательная оптимизация первого этапа. На этапе 2 (ZoneMasks) борода
просто остаётся в `face_dark` с минимальной дельтой ±5, что безопасно. Уточнение
можно добавить на этапе 3, когда face_dark correction станет точнее.

### TDD-дисциплина

Каждый шаг реализации следует циклу Red-Green-Refactor:

1. **RED**: написать тест, который проваливается. Тест описывает ожидаемое
   поведение, которого ещё нет. Для баг-фиксов — тест воспроизводит баг.
2. **GREEN**: написать минимальную реализацию, которая проходит все тесты.
   Не оптимизировать, не рефакторить — только сделать тесты зелёными.
3. **REFACTOR**: улучшить код, сохраняя зелёные тесты. Удалить дублирование,
   улучшить имена, упростить логику.

Правила:
- Тест на баг пишется первым и воспроизводит текущее (неправильное) поведение.
- Контрактные тесты (дизъюнктность зон, envelope лимиты, consistency) пишутся
  до реализации контракта.
- Интеграционные тесты пишутся после юнит-тестов всех компонентов.
- Performance-тесты (memory budget, time budget) не блокируют RED/GREEN.
  Они пишутся в отдельной фазе PERF после GREEN: если тест падает, это не
  отменяет GREEN, но блокирует merge в main до устранения регресса.
- Все новые тесты запускаются в CI. Если существующий тест ломается из-за
  изменения поведения — тест обновляется с явным комментарием why.

Структура тестов:
```text
tests/
  test_pipeline_plan.py          — PipelinePlan, profiles, validate_plan
  test_zone_masks.py             — ZoneMasks, resolve_zone_priority, beard
  test_safety_envelope.py        — envelope limits, clipping, degradation
  test_quality_gates.py          — pre/post-check gates
  test_soft_rolloff.py           — soft_rolloff_masked helper
  test_zonal_correction.py       — skin delta, face_dark correction
  test_preview_export_consistency.py — oval/zone consistency
  test_dither_regression.py      — 1-bit regression on curated set
  test_step_metrics.py           — StepMetricsRecord, ZoneMetrics
  test_bugfixes_a.py             — soft knee fix, unsharp clamp fix (extend)
  test_pipeline.py               — pipeline with profiles (extend)
  test_face_region.py            — hair_mask diagnostics (extend)
  test_config_defaults_sync.py   — config sync step (extend)
  test_memory.py                 — zone masks memory 8K (extend)
```

## Этап 0. Блокеры перед продом

Цель: убрать явные дефекты, которые могут портить результат уже сейчас.

### Синхронизировать config defaults

Это отдельный блокер, а не мелкая правка документации. Если UI показывает одни
значения, а backend применяет другие, оператор не может доверять настройкам.

Нужен один источник правды для дефолтов. Frontend `config-defaults.json` должен
генерироваться из Python `DEFAULTS` через явный export adapter, а не
поддерживаться вручную. Adapter нужен потому, что frontend-формат может
отличаться от внутреннего backend-конфига.

Критерий готовности:

- `config.yaml`, Python `DEFAULTS` и frontend defaults синхронизированы;
- CI проверяет, что сгенерированный frontend defaults не отличается от файла;
- документация обновлена под реальные значения;
- рассинхрон дефолтов становится ошибкой тестов.

### Исправить soft knee в postprocess

Заменить chained indexing на явное изменение временного массива:

```python
masked = arr[mask_bool]
over = masked > knee
masked[over] = knee + (masked[over] - knee) * 0.35
arr[mask_bool] = np.clip(masked, 0, white_ceiling)
```

Критерий готовности:

- тест доказывает, что значения выше knee реально сжимаются;
- тест доказывает, что hard plateau уменьшается.

### Убрать hard clamp из unsharp или заменить на soft rolloff

`unsharp` не должен сам жёстко резать значения до `white_ceiling`. Лучше:

- либо убрать ceiling из `apply_unsharp_mask()`;
- либо заменить на общий helper `soft_rolloff_masked()`.

Критерий готовности:

- после unsharp не появляется массив пикселей с одинаковым ceiling;
- финальный ceiling применяется только одним контролируемым способом.

### Ограничить shadow floor для laser

Для laser-режимов `shadow_floor` не должен применяться ко всей маске субъекта.
Полное отключение тоже рискованно: в 1-bit режиме нулевые тени могут давать
дыры при дизеринге.

Безопасный первый шаг: применять laser floor только к `face_dark` или
контурной зоне, но не к `hair` и `clothes`. До появления `ZoneMasks` это можно
сделать пересечением с `face_mask`.

Критерий готовности:

- глубокие тени волос и одежды laser не поднимаются автоматически;
- тени лица не проваливаются в 0 там, где это ломает engraving/dithering;
- impact сохраняет свою логику needle floor.

### Подключить hair mask в diagnostics

В проекте уже есть `generate_hair_mask()` в `face_region.py`, но пайплайн не
использует эту маску как отдельную зону. Минимальный шаг до полноценного
zonal refactor: начать строить `hair_mask` и показывать её в diagnostics.

Критерий готовности:

- волосы не попадают в будущую `clothes`-зону;
- диагностика может отдельно считать метрики волос и одежды;
- hair-зона помечается как approximate;
- diagnostics показывает anomaly flag, если hair-зона подозрительно велика
  или мала для данного субъекта.

Degradation contract: если `hair_mask` ненадёжна, зона деградирует в
`clothes`, а не в `face_skin` или `face_dark`. Ошибка маски должна приводить к
меньшему вмешательству, а не к агрессивной коррекции волос, шапки или бороды.

### Документация

- README.md: обновить секцию конфигурации — указать, что Python DEFAULTS = single source of truth
- CHANGELOG.md: добавить записи о фиксе soft knee, unsharp clamp, laser shadow floor, hair mask в diagnostics
- config.yaml: обновить дефолты при рассинхронизации с Python DEFAULTS
- docs/reference/config.md: описать параметры shadow_floor для laser vs impact
- docs/troubleshooting.md: новый документ — расшифровка diagnostics warnings (hair_anomaly, soft_knee_inactive)

## Этап 1. Безопасный минимальный пайплайн

Цель: получить режим, который почти не портит исходную AI-ретушь.

### Ввести PipelinePlan как раннюю обёртку

Перед добавлением профилей и quality gates нужен слой принятия решений:

```python
PipelinePlan(
    profile="preserve",
    active_steps={...},
    skin_delta=...,
    highlight_rolloff=...,
    glow_size=...,
    unsharp_percent=...,
)
```

На этом этапе `PipelinePlan` не требует перестановки файлов. Он может жить
рядом с текущим `pipeline.py` и описывать, какие шаги будут применены.

Критерий готовности:

- параметры шагов можно протестировать без обработки изображения;
- diagnostics может показать не только факт обработки, но и план обработки;
- будущие профили и gates не добавляют новый набор `if/else` в pipeline.

### Добавить processing profile

Ввести режимы:

- `preserve` — минимальное вмешательство;
- `standard` — текущая логика после исправлений;
- `diagnostic` — сохраняет промежуточные маски и метрики.

Для `preserve`:

```text
chromakey -> grayscale -> optional glow -> soft highlight rolloff -> vignette -> export
```

Без глобальных levels, без face correction, без unsharp по умолчанию.

Профиль и пресет должны быть ортогональными:

- профиль задаёт множество активных шагов и ограничения на агрессивность;
- пресет задаёт machine-specific параметры для активных шагов;
- `preserve + laser_80w` означает параметры `laser_80w`, но безопасный набор
  шагов;
- `diagnostic + impact` означает параметры impact и расширенный сбор масок,
  step metrics и warnings;
- если профиль отключил `levels`, то `target_pre_fb` из пресета игнорируется
  для этого запуска.

Критерий готовности:

- оператор может выбрать режим без агрессивной автокоррекции;
- preview/export совпадают по выбранному режиму.

### API и UI implications

Новые элементы интерфейса, следующие из этого этапа:

- **Profile selector** — dropdown в UI для выбора `preserve` / `standard` /
  `diagnostic`. По умолчанию `standard` для обратной совместимости.
- **Step metrics panel** — в diagnostics: таблица или timeline с метриками
  до/после каждого шага.
- **Warnings badge** — индикатор сработавших gates и `ValidatedPlan` warnings
  в результатах обработки.

API: новые поля `profile` (optional, default `standard`) и `step_metrics`
в ответе `/process`. Запросы без `profile` обрабатываются как `standard`.

### Добавить step metrics

После каждого ключевого шага считать:

- median/p95/max по `face_skin`;
- variance по `face_skin`;
- clipped percentage по subject и face;
- shadow crush по subject;
- tonal range по face и subject.

Хранение: `step_metrics: List[StepMetricsRecord]` в `PipelineResult`, где:

```python
@dataclass
class ZoneMetrics:
    median: float
    p10: float
    p90: float
    p95: float
    max: float
    variance: float
    clipped_pct: float

@dataclass
class StepMetricsRecord:
    step_name: str                         # "glow", "levels", "face_correction", ...
    timestamp_ms: int                      # время относительно начала пайплайна
    zone_metrics: dict[str, ZoneMetrics]   # {"face_skin": ZoneMetrics(...), ...}
    warnings: list[str]                    # gate warnings, если сработали
```

Отсутствующие зоны — отсутствие ключа, не `None`. Сериализация — через
существующую Pydantic-схему diagnostics для отображения в UI и API.

Критерий готовности:

- diagnostics показывает не только финал, но и изменение по шагам;
- можно увидеть, какой шаг ухудшил результат.

### Зафиксировать preview/export consistency

`process_preview()` работает на уменьшенном изображении, а export на полном
разрешении. Для zonal-логики это риск: маски и пороги могут отличаться.
Consistency нужно проверять после каждого этапа, который меняет маски,
масштабирование или параметры, а не только в конце рефакторинга.

#### Механизм consistency

1. **Face oval — единый источник.** После первой детекции (или ручной правки в
   UI) `face_oval` сохраняется в `PipelineContext` как нормализованные
   координаты (доли ширины/высоты). Preview и export используют один и тот же
   `face_oval` — повторная автодетекция запрещена.
2. **Маски строятся от нормализованного овала.** `face_mask` генерируется из
   нормализованного овала, scaled под текущее разрешение. Все остальные маски
   (`hair`, `clothes`, `contour`) строятся от `face_mask` того же разрешения,
   а не от повторной детекции.
3. **Пороги — одинаковые.** Chromakey threshold, skin threshold и contour
   gradient threshold — это параметры плана, а не результат анализа конкретного
   разрешения. Они не пересчитываются для preview.
4. **Downscale только после chromakey.** Изображение уменьшается для preview
   после удаления хромакея, но до построения зон. Зоны строятся от
   уменьшенного grayscale с теми же порогами, что гарантирует идентичную
   логику классификации (но не попиксельную маску).
5. **Assert в diagnostics.** Если `face_oval` в preview и export различается
   более чем на 2% по любой координате — diagnostics показывает warning и
   флаг `consistency_mismatch`.

Критерий готовности:

- `face_oval` передаётся из preview в export через `PipelineContext`, а не
  детектируется заново;
- diagnostics логирует scale ratio preview и export;
- diagnostics показывает warning при расхождении овала >2%;
- тест `test_preview_export_zones_consistent` создаёт preview и export из
  одного изображения и проверяет, что зоны не расходятся более чем на 5%
  площади (допуск на интерполяцию при downscale).

### Документация

- README.md: добавить секцию про профили обработки (preserve/standard/diagnostic) и шаги пайплайна
- CHANGELOG.md: записи о PipelinePlan, профилях, step metrics, preview/export consistency
- docs/reference/api.md: добавить поля `profile` и `step_metrics` в ответ `/process`
- docs/architecture/pipeline.md: обновить диаграмму пайплайна с профилями и PipelinePlan

## Этап 2. Автоматические зоны без ручной разметки

Цель: заменить глобальную коррекцию на zonal-метрики.

### Ввести ZoneMasks

Добавить модуль, например `retouch/processing/zones.py`.

Структура:

```python
@dataclass
class ZoneMasks:
    subject: np.ndarray
    face: np.ndarray
    hair: np.ndarray
    face_skin: np.ndarray
    face_dark: np.ndarray
    clothes: np.ndarray
    highlights: np.ndarray
    contour_inner: np.ndarray
    contour_outer: np.ndarray
    background: np.ndarray
```

Источники:

- `subject_mask` из chromakey;
- `face_mask` из овала;
- `hair_mask` из `generate_hair_mask()`;
- grayscale brightness;
- gradient/alpha mask chromakey для `contour_inner` и `contour_outer`;
- простые morphology operations только как fallback.

Критерий готовности:

- зоны строятся без ручной разметки;
- если овал лица неверный, оператор правит только овал;
- пересекающиеся зоны разрешаются по зафиксированному приоритету.
- `hair_mask` из этапа 0 становится `ZoneMasks.hair`;
- diagnostics использует `ZoneMasks` как единый источник масок.
- если `face_mask` не построен → diagnostics error `face_not_detected` →
  пайплайн не продолжается. Hard fail, без fallback в `subject_only` режим.

### Сделать skin threshold адаптивным

Абсолютный `skin_threshold=100` слишком хрупкий. Он ошибается на тёмной коже,
бороде, усах и сильном боковом свете.

Базовая формула должна быть двухпроходной, чтобы волосы и брови внутри овала
не занижали порог кожи:

```text
coarse_skin = face_pixels where gray >= absolute_skin_min
robust_face_center = median(coarse_skin) or histogram_mode(coarse_skin)
adaptive_skin_threshold = clamp(robust_face_center - delta, min_value, max_value)
```

Абсолютное значение из конфига можно оставить как fallback или нижнюю границу.
`histogram_mode` реализуется без scipy: `np.bincount()` по uint8-яркости.
**Важно: сырой `np.bincount()` даёт шумный mode для малых зон.** Требуется
сглаживание — простая свёртка `np.convolve(hist, [0.25, 0.5, 0.25], mode='same')`
или `uniform_filter1d` из scipy.ndimage (если scipy доступен). Без сглаживания
mode может прыгать на ±5 уровней от кадра к кадру, что делает адаптивный порог
недетерминированным в глазах оператора.

Существующий `face_skin_threshold` сохраняется для обратной совместимости как
`absolute_skin_min` и нижняя граница адаптивного расчёта. Ручной override
полного threshold допускается только в advanced/diagnostic режиме.

Критерий готовности:

- тёмная кожа не выпадает целиком в `face_dark`;
- светлые волосы и борода не захватываются как кожа без ограничений;
- поведение покрыто synthetic-тестами;
- existing test suite проходит или обновлён под явное изменение поведения.

### Разделить analytics по зонам

Вместо одного dict `analytics` сделать:

```python
analytics["face_skin"]
analytics["face_dark"]
analytics["hair"]
analytics["clothes"]
analytics["highlights"]
analytics["subject"]
```

Для каждой зоны считать median, p10, p90, p95, max, variance, clipped_pct.

Критерий готовности:

- glow не использует метрики кожи как метрики всего субъекта;
- levels не использует одежду для решения по лицу;
- highlight rolloff видит реальные светлые зоны;
- existing test suite проходит или обновлён под явное изменение поведения.

### Сохранить batch numpy pass

Зональные коррекции не должны превращаться в серию PIL -> numpy -> PIL
конверсий. Все маски строятся один раз, а операции применяются в одном массиве.

Пример с учётом приоритета зон:

```python
primary_zone = resolve_zone_priority(zones)
arr[primary_zone.face_skin] = apply_skin(arr[primary_zone.face_skin], plan.skin_delta)
arr = apply_final_highlight_rolloff(arr, zones.highlights, plan.highlight_rolloff)
```

Критерий готовности:

- одна конверсия изображения в numpy на группу тональных операций;
- порядок операций не меняет результат для пересекающихся зон;
- performance-тест на большом изображении не показывает кратный регресс.

### Ввести safety envelope

Safety envelope — это максимальная допустимая дельта, которую пайплайн может
внести в каждую зону до quality gates.

Базовая политика:

- `face_skin`: не больше ±15 уровней;
- `face_dark`: не больше ±5 уровней;
- `hair`: 0 или не больше ±3 уровней;
- `clothes`: 0, не менять по решению лица;
- `highlights`: только rolloff, без подъёма;
- `contour_inner`: только glow/edge logic;
- `contour_outer`: только антифринги/фон, без тональной коррекции субъекта.

Значения эмпирические: ±15 на 256-шкале — это ~6%, что едва заметно на
гравировке. Требуют калибровки на sample set из 10-15 реальных заказов.
Доступны для переопределения через config.yaml (секция `safety_envelope`).

Presets задают machine-specific hard envelope. Gates могут только ослаблять
параметры внутри envelope, но не выходить за него. Все ослабления пишутся в
diagnostics.

Критерий готовности:

- нет скрытого выхода за параметры пресета;
- оператор видит, какие параметры были ослаблены;
- existing test suite проходит или обновлён под явное изменение поведения.

### Добавить PipelinePlan validation

После появления зон и safety envelope каждый план проходит валидацию:

```python
validated = validate_plan(plan, profile, preset, zones, envelope)
```

`ValidatedPlan` клипует параметры до лимитов профиля и safety envelope,
отключает шаги, запрещённые профилем, и возвращает warnings для diagnostics.

`validate_plan()` работает с dataclass; Pydantic-схема (`PipelinePlanSchema`,
`ValidatedPlanSchema`) добавляется только на этапе 6 для API-сериализации
и не дублирует логику валидации.

Примеры правил:

- `skin_delta=50` клипуется до `max_skin_delta`;
- `profile=preserve` отключает `unsharp`, даже если пресет задаёт percent;
- gates могут ослабить `stone_gamma`, но только в пределах preset envelope;
- конфликт `highlight_rolloff` и `white_ceiling` решается в пользу rolloff.

Правило для rolloff и ceiling: rolloff заменяет hard ceiling как основную
тональную операцию, но финальный `np.clip(..., 0, white_ceiling)` остаётся
страховкой. Цель rolloff — уменьшить число пикселей, которые реально доходят
до safety clip.

Критерий готовности:

- невалидный plan не попадает в pixel operations;
- все клипнутые параметры видны в diagnostics;
- existing test suite проходит или обновлён под явное изменение поведения.

### Документация

- README.md: добавить секцию про зоны и профили, обновить описание пайплайна
- CHANGELOG.md: записи о ZoneMasks, адаптивном skin threshold, safety envelope, validate_plan
- config.yaml: добавить секции `safety_envelope` и `profile` с дефолтами
- docs/zones.md: новый документ — описание зон, формулы, приоритеты, fallback-стратегии, борода/усы
- docs/reference/api.md: описать новые поля zonal analytics и ValidatedPlan warnings

## Этап 3. Замена глобального Levels

Цель: убрать основной источник деградации.

### Заменить factor на ограниченную дельту

Вместо:

```text
corrected = arr * factor
```

использовать двустороннюю формулу с явным target range:

```text
if median < target_min:
    target_delta = min(target_min - median, max_delta)   # мягкое осветление
elif median > target_max:
    target_delta = max(target_max - median, -max_delta)  # затемнение
else:
    target_delta = 0  # в диапазоне, не трогаем
```

`max_delta` ограничивается safety envelope (±15 для face_skin).
Применять delta только к `face_skin` и только с весом, зависящим от яркости.

Пример политики:

- кожа: мягкая коррекция, максимум 10-15 уровней;
- волосы/брови: не трогать или максимум 3-5 уровней;
- одежда: не осветлять по решению лица;
- highlights: только rolloff, без подъёма;
- contour: только glow/edge logic.

Критерий готовности:

- чёрная одежда не светлеет из-за лица;
- волосы не становятся серыми;
- кожа корректируется мягко и локально;
- если `face_dark` меньше 5% от `face_mask`, его коррекция ослабляется или
  пропускается;
- existing test suite проходит или обновлён под явное изменение поведения.

### Проверить влияние на 1-bit dithering

Zonal rolloff и skin-only correction меняют тональный диапазон, а значит могут
менять паттерн Jarvis/Stucki при `export_mode=1bit`.

Критерий готовности:

- 8-bit preview не является единственным критерием качества;
- для 1-bit экспорта есть dither preview до/после;
- dither preview сравнивается на curated sample set;
- минимальный curated set: 5-10 фиксированных изображений из тестовых fixtures;
- эталоны хранятся в репозитории и обновляются вручную при осознанном
  изменении тональной логики;
- CI запускает dither regression на curated set, чтобы регрессии не находились
  только на production-заказах;
- тесты или ручные эталоны фиксируют отсутствие новых артефактов.

### Face brightness сделать честным

Варианты:

1. Только затемнение:
   - переименовать target в `face_brightness_max`;
   - убрать `target_min` из UI как управляющий параметр.

2. Мягкое осветление:
   - разрешить осветление только `face_skin`;
   - ограничить delta;
   - не трогать highlights и hair.

Рекомендуемый вариант: мягкое осветление только кожи с жёстким лимитом delta.

Критерий готовности:

- тёмная кожа может быть слегка поднята;
- блики и волосы не пересвечиваются;
- target range снова соответствует поведению.

### Документация

- README.md: обновить описание Levels — теперь skin-only bounded correction вместо factor
- CHANGELOG.md: записи о замене factor на delta, face brightness fix, dither regression
- docs/zones.md: добавить формулу bounded delta и примеры политики коррекции по зонам
- docs/troubleshooting.md: добавить секцию про диагностику 1-bit dither артефактов

## Этап 4. Единая логика ceiling и rolloff

Цель: убрать несколько конкурирующих потолков.

### Ввести общий helper

Например:

```python
soft_rolloff_masked(arr, mask, knee, ceiling, compression)
```

Все шаги используют его вместо локального `np.minimum()` и `np.clip()`.
`compression` должен быть параметром конфига или `PipelinePlan`, а не
разным хардкодом `0.50` и `0.35` в разных модулях.

Критерий готовности:

- ceiling применяется предсказуемо;
- нет нескольких разных реализаций clamp;
- тесты покрывают отсутствие plateau.

### Rolloff только по нужным зонам

Для светов использовать `highlights` или `face_skin & bright_pixels`, а не весь
subject.

Критерий готовности:

- воротник и лоб не превращаются в плоскую белую массу;
- детали кожи сохраняют variance.

### Документация

- README.md: обновить секцию про ceiling — единый helper soft_rolloff_masked
- CHANGELOG.md: записи о soft_rolloff_masked, zonal rolloff
- docs/zones.md: добавить формулу rolloff и описание параметра compression
- config.yaml: добавить параметр `compression` (заменить хардкод 0.50/0.35)

## Этап 5. Quality gates и pre-check

Цель: пайплайн не должен молча ухудшать изображение.

Предпочтительная модель: не откатывать плохой шаг после применения, а заранее
проверять `PipelinePlan` и выбирать безопасные параметры.

После каждого шага всё равно нужно сравнивать метрики до/после, но это должно
быть страховкой и диагностикой, а не основным способом управления.

### Спецификация порогов gates

Правила применяются до шага (pre-check) и после (post-check):

| Правило | Тип | Порог | Действие |
|---------|-----|-------|----------|
| variance loss по `face_skin` | post | > 35% | ослабить delta текущего шага на 50% |
| clipped_pct по subject | post | > 5% | уменьшить rolloff/ceiling на 20% |
| p95 shift по face_skin | post | > 20 уровней | ослабить delta на 50% |
| shadow crush по subject | post | > 10% pixels < 5 | не применять floor/gamma к этой зоне |
| skin_delta exceeds envelope | pre | > max_skin_delta | клипнуть до envelope |
| face_dark < 5% от face_mask | pre | < 5% | пропустить face_dark correction |
| contour_inner > 30% subject | pre | > 30% | fallback на morphological contour |

Все ослабления и сработавшие gates записываются в diagnostics с указанием:
gate_name, step_name, original_value, adjusted_value, reason.

Критерий готовности:

- агрессивный шаг ослабляется до применения;
- diagnostics объясняет, какой gate сработал;
- existing test suite проходит или обновлён под явное изменение поведения.

### Документация

- README.md: добавить секцию про quality gates и pre-check модель
- CHANGELOG.md: записи о quality gates, pre/post-check правилах
- docs/reference/api.md: описать gate warnings в ответе API
- docs/troubleshooting.md: добавить расшифровку всех gate warnings (variance_loss, clipped_pct, p95_shift, shadow_crush)

## Этап 6. Полный рефакторинг структуры

Цель: сделать пайплайн расширяемым и проверяемым.

Важно: перестановка файлов должна идти последней. Сначала нужно ввести
`PipelinePlan`, профили, зоны и gates поверх текущей структуры, чтобы не
сломать API, UI и существующие тесты большим рефакторингом.

### Разделить pipeline на стадии

Предлагаемая структура:

```text
segmentation/
  chromakey.py
  face_region.py
  zones.py

analysis/
  zone_metrics.py
  quality_gates.py

correction/
  skin_tone.py
  highlights.py
  contour.py
  stone_response.py

export/
  bmp.py
  dither.py
```

`pipeline.py` должен оркестрировать шаги, а не содержать тональную логику.

**Миграция импортов:** при переносе файлов — re-export из старых путей
(`retouch.processing.levels`, `retouch.processing.glow` и т.д.) на переходный
период 6 месяцев. После — deprecation warning, затем удаление. Это сохранит
обратную совместимость для CLI, API и внешних скриптов.

### Расширить PipelinePlan для API

К этому этапу базовый `PipelinePlan` уже должен существовать. Здесь его нужно
расширить для сериализации в FastAPI diagnostics и UI:

```python
PipelinePlan(
    skin_delta=...,
    highlight_rolloff=...,
    glow_size=...,
    unsharp_percent=...,
)
```

План можно показать в diagnostics и протестировать без обработки картинки.
Для API нужна стабильная Pydantic-схема, чтобы frontend мог показать активные
шаги, ослабленные параметры и сработавшие gates.

Внутренняя реализация может оставаться dataclass, но сериализуемая часть
должна иметь Pydantic-модель: `PipelinePlanSchema` и `ValidatedPlanSchema`.

Критерий готовности:

- решение пайплайна отделено от применения пиксельных операций;
- проще объяснять оператору, что будет сделано;
- проще тестировать без эталонных изображений;
- backend и frontend получают сериализуемый план.
- existing test suite проходит или обновлён под явное изменение поведения.

### Документация

- README.md: обновить структуру проекта — новые директории segmentation/, analysis/, correction/, export/
- CHANGELOG.md: записи о рефакторинге структуры, re-export переходном периоде, Pydantic-схемах
- docs/architecture/pipeline.md: обновить архитектурную диаграмму под новую структуру модулей
- docs/reference/api.md: описать PipelinePlanSchema и ValidatedPlanSchema в API
- docs/zones.md: обновить пути импортов после миграции

## Рекомендуемый порядок работ

1. Синхронизировать config/docs/defaults и frontend defaults.
   TDD:
     RED:
       - test_config_defaults_sync.py::test_frontend_json_matches_python_defaults — проваливается, если JSON и DEFAULTS расходятся
       - test_config_defaults_sync.py::test_all_machine_keys_present — проваливается, если в JSON нет ключа станка
       - test_config_defaults_sync.py::test_export_defaults_generates_valid_json — проваливается, если export adapter ещё не существует
     GREEN:
       - scripts/export_defaults.py генерирует актуальный JSON из DEFAULTS
       - CI-скрипт сравнивает сгенерированный файл с коммиченным
     REFACTOR:
       - проверить, что adapter корректно маппит форматы frontend/backend
       - параметризовать тесты для всех MACHINE_TYPES
   Документация:
       - README.md: обновить секцию конфигурации, указать Python DEFAULTS = single source of truth
       - CHANGELOG.md: «Config defaults sync: Python DEFAULTS = single source of truth»
       - config.yaml: обновить дефолты при расхождении

2. Исправить soft knee bug в `pipeline.py`.
   TDD:
     RED:
       - test_bugfixes_a.py::test_soft_knee_values_above_knee_are_compressed — воспроизводит баг: значения выше knee не сжимаются
       - test_bugfixes_a.py::test_soft_knee_no_hard_plateau — воспроизводит баг: plateau на ceiling (много одинаковых значений)
       - test_bugfixes_a.py::test_soft_knee_chained_indexing_writes_back — проверяет, что результат записывается в исходный массив
     GREEN:
       - исправить chained indexing на временный массив (как в плане)
     REFACTOR:
       - параметризовать compression ratio (0.35) для будущего soft_rolloff_masked
       - вынести константу в конфиг
   Документация:
       - CHANGELOG.md: «Fix: soft knee in postprocess actually compresses highlights»

3. Убрать hard clamp из unsharp.
   TDD:
     RED:
       - test_bugfixes_a.py::test_unsharp_no_hard_ceiling_plateau — воспроизводит: после unsharp массив пикселей с одинаковым ceiling
       - test_bugfixes_a.py::test_unsharp_preserves_variance_above_knee — проваливается, если unsharp убивает variance в светах
     GREEN:
       - убрать ceiling из apply_unsharp_mask() или заменить на soft rolloff
     REFACTOR:
       - убедиться, что финальный ceiling применяется только один раз
       - подготовить почву для единого soft_rolloff_masked (шаг 15)
   Документация:
       - CHANGELOG.md: «Fix: unsharp no longer hard-clips to white_ceiling»
       - docs/reference/config.md: обновить описание unsharp parameters

4. Подключить `hair_mask` в пайплайн и diagnostics.
   TDD:
     RED:
       - test_face_region.py::test_hair_mask_in_diagnostics — проваливается, если hair_mask не возвращается в diagnostics
       - test_face_region.py::test_hair_mask_anomaly_flag — проваливается, если anomaly flag не генерируется для подозрительно большой/малой зоны
       - test_face_region.py::test_hair_mask_degradation_to_clothes — проваливается, если ненадёжная hair_mask деградирует не в clothes
     GREEN:
       - вызвать generate_hair_mask() в пайплайне и добавить в diagnostics
       - добавить anomaly detection (слишком большая/малая зона)
       - реализовать degradation contract
     REFACTOR:
       - вынести anomaly thresholds в конфиг
       - добавить метрики hair-зоны в analytics dict
   Документация:
       - CHANGELOG.md: «Feature: hair mask connected to pipeline diagnostics»
       - docs/troubleshooting.md: расшифровка hair_anomaly warning

5. Ввести `PipelinePlan` как dataclass без перестановки файлов.
   TDD:
     RED:
       - test_pipeline_plan.py::test_pipeline_plan_constructs_with_defaults — проваливается, если PipelinePlan не существует
       - test_pipeline_plan.py::test_pipeline_plan_active_steps_dict — проваливается, если active_steps не задаёт множество шагов
       - test_pipeline_plan.py::test_pipeline_plan_profiles_orthogonal_to_presets — проваливается, если профиль зависит от пресета
     GREEN:
       - реализовать PipelinePlan dataclass с полями profile, active_steps, skin_delta, highlight_rolloff, glow_size, unsharp_percent
       - добавить фабричные методы для standard/preserve/diagnostic
     REFACTOR:
       - проверить, что план можно сериализовать в diagnostics без обработки изображения
       - убедиться, что pipeline.py использует PipelinePlan вместо разбросанных if/else
   Документация:
       - CHANGELOG.md: «Feature: PipelinePlan dataclass introduced»
       - docs/architecture/pipeline.md: обновить архитектуру с PipelinePlan

6. Добавить профили `preserve`, `standard`, `diagnostic` через `PipelinePlan`.
   TDD:
     RED:
       - test_pipeline_plan.py::test_profile_preserve_disables_levels_and_unsharp — проваливается, если preserve не отключает levels/unsharp
       - test_pipeline_plan.py::test_profile_standard_matches_current_behavior — проваливается, если standard не сохраняет текущую логику
       - test_pipeline_plan.py::test_profile_diagnostic_keeps_intermediates — проваливается, если diagnostic не сохраняет промежуточные
       - test_pipeline.py::test_pipeline_with_preserve_profile — проваливается, если пайплайн не принимает profile параметр
     GREEN:
       - реализовать профили как предустановки active_steps в PipelinePlan
       - добавить параметр profile в process_steps / process_preview / process_export
     REFACTOR:
       - параметризовать тесты пайплайна для всех трёх профилей
       - убедиться в ортогональности профиля и пресета
   Документация:
       - README.md: добавить секцию про профили обработки
       - CHANGELOG.md: «Feature: processing profiles (preserve/standard/diagnostic)»
       - docs/reference/api.md: добавить поле profile в API

7. Добавить step metrics.
   TDD:
     RED:
       - test_step_metrics.py::test_zone_metrics_dataclass_fields — проваливается, если ZoneMetrics не существует
       - test_step_metrics.py::test_step_metrics_record_dataclass_fields — проваливается, если StepMetricsRecord не существует
       - test_step_metrics.py::test_step_metrics_after_each_step — проваливается, если pipeline не собирает step_metrics
       - test_step_metrics.py::test_missing_zone_is_absent_key_not_none — проваливается, если отсутствующая зона = None вместо отсутствия ключа
     GREEN:
       - реализовать ZoneMetrics и StepMetricsRecord dataclass-ы
       - добавить сбор метрик после каждого ключевого шага в pipeline
       - добавить step_metrics в PipelineResult
      REFACTOR:
        - вынести сбор метрик в helper-функцию compute_zone_metrics(arr, mask)
        - Начиная с шага 8, каждый этап, который меняет маски или параметры,
          включает consistency-assert (см. п. 16).
   Документация:
       - CHANGELOG.md: «Feature: step metrics collection after each pipeline step»
       - docs/reference/api.md: описать step_metrics в ответе API

8. Ввести `ZoneMasks`, `contour_inner`/`contour_outer` и adaptive skin threshold
   одним логическим блоком. Эти три подзадачи тесно связаны: contour и threshold
   влияют на корректность ZoneMasks, и раздельная реализация создаст
   промежуточное состояние с неверными масками.
   TDD:
     RED:
       - test_zone_masks.py::test_zone_masks_dataclass_fields — проваливается, если ZoneMasks не существует
       - test_zone_masks.py::test_resolve_zone_priority_disjoint — проваливается, если маски пересекаются после resolve
       - test_zone_masks.py::test_resolve_zone_priority_covers_subject — проваливается, если приоритизированные маски не покрывают subject
       - test_zone_masks.py::test_contour_inner_from_gradient — проваливается, если contour_inner не строится из gradient
       - test_zone_masks.py::test_contour_outer_from_gradient — проваливается, если contour_outer не строится из gradient
       - test_zone_masks.py::test_contour_fallback_when_gradient_bad — проваливается, если нет fallback при contour_inner > 30% subject
       - test_zone_masks.py::test_adaptive_skin_threshold_dark_skin — проваливается, если тёмная кожа выпадает в face_dark
       - test_zone_masks.py::test_adaptive_skin_threshold_bright_hair_not_skin — проваливается, если светлые волосы захватываются как кожа
       - test_zone_masks.py::test_histogram_mode_smoothed — проваливается, если mode без сглаживания даёт нестабильный результат
       - test_zone_masks.py::test_face_not_detected_hard_fail — проваливается, если face_mask=None позволяет пайплайну продолжаться
       - test_zone_masks.py::test_beard_suspected_reclassification — проваливается, если борода не переклассифицируется в hair
     GREEN:
       - реализовать ZoneMasks dataclass с 9 масками
       - реализовать resolve_zone_priority() по контракту дизъюнктного разбиения
       - реализовать contour_inner/contour_outer из gradient с fallback
       - реализовать adaptive_skin_threshold с двухпроходной формулой и сглаженным mode
       - реализовать beard_suspected проверку и переклассификацию
     REFACTOR:
       - вынести gradient → contour в отдельную функцию с параметром порога
       - проверить, что hair_mask из этапа 0 становится ZoneMasks.hair
       - memory: проверить порядок построения (subject+face+gray → hair → contour → highlights → clothes → resolve → del)
   Документация:
       - CHANGELOG.md: «Feature: ZoneMasks, adaptive skin threshold, contour zones»
       - docs/zones.md: новый документ — описание зон, формулы, приоритеты, fallback-стратегии

9. Переписать analytics на zonal metrics.
   TDD:
     RED:
       - test_zone_masks.py::test_analytics_per_zone_keys — проваливается, если analytics не содержит ключей face_skin/face_dark/hair/clothes/highlights
       - test_zone_masks.py::test_analytics_per_zone_metrics — проваливается, если зональные метрики не содержат median/p10/p90/p95/max/variance/clipped_pct
       - test_zone_masks.py::test_glow_uses_skin_metrics_not_subject — проваливается, если glow берёт метрики субъекта вместо кожи
     GREEN:
       - заменить глобальный analytics dict на зональный
       — обновить потребителей метрик (glow, levels, rolloff) на чтение из правильных зон
     REFACTOR:
       — переиспользовать compute_zone_metrics из шага 7
       — убедиться, что все шаги пайплайна читают метрики из правильных зон
   Документация:
       - CHANGELOG.md: «Refactor: analytics split by zones (face_skin, hair, clothes, highlights)»
       - docs/reference/api.md: обновить структуру analytics в ответе API

10. Ввести safety envelope.
    TDD:
      RED:
        - test_safety_envelope.py::test_envelope_face_skin_delta_max_15 — проваливается, если envelope не ограничивает face_skin ±15
        - test_safety_envelope.py::test_envelope_face_dark_delta_max_5 — проваливается, если envelope не ограничивает face_dark ±5
        - test_safety_envelope.py::test_envelope_clothes_zero_delta — проваливается, если clothes допускает изменение по решению лица
        - test_safety_envelope.py::test_envelope_highlights_rolloff_only — проваливается, если highlights допускает подъём
        - test_safety_envelope.py::test_envelope_from_config_yaml — проваливается, если envelope не читается из конфига
        - test_safety_envelope.py::test_envelope_degradation_contract — проваливается, если ненадёжная маска деградирует в более агрессивную зону
      GREEN:
        - реализовать SafetyEnvelope dataclass с лимитами по зонам
        - добавить секцию safety_envelope в config.yaml
        - реализовать чтение envelope из конфига с дефолтами
      REFACTOR:
        - калибровка значений на sample set из 10-15 реальных заказов
        - параметризовать все лимиты через конфиг
    Документация:
        - CHANGELOG.md: «Feature: safety envelope per zone with config overrides»
        - config.yaml: добавить секцию safety_envelope с дефолтами
        - docs/zones.md: добавить таблицу safety envelope лимитов

11. Добавить `ValidatedPlan` и `validate_plan()`.
    TDD:
      RED:
        - test_pipeline_plan.py::test_validate_plan_clips_skin_delta — проваливается, если skin_delta=50 не клипуется до max_skin_delta
        - test_pipeline_plan.py::test_validate_plan_preserve_disables_unsharp — проваливается, если preserve + unsharp_percent > 0 не отключается
        - test_pipeline_plan.py::test_validate_plan_rolloff_vs_ceiling — проваливается, если rolloff и ceiling конфликт не решается в пользу rolloff
        - test_pipeline_plan.py::test_validate_plan_returns_warnings — проваливается, если клипнутые параметры не видны в warnings
        - test_pipeline_plan.py::test_invalid_plan_does_not_reach_pixel_ops — проваливается, если невалидный план проходит в pixel operations
      GREEN:
        - реализовать validate_plan(plan, profile, preset, zones, envelope)
        - реализовать ValidatedPlan с клипнутыми параметрами и warnings
        - вставить validate_plan в pipeline до пиксельных операций
      REFACTOR:
        - убедиться, что все клипнутые параметры логируются в diagnostics
        - проверить, что validate_plan работает с dataclass (не Pydantic)
    Документация:
        - CHANGELOG.md: «Feature: ValidatedPlan with parameter clipping and warnings»
        - docs/reference/api.md: описать ValidatedPlan warnings в ответе API

12. Добавить pre-check quality gates — сразу после ValidatedPlan, до тональной
    логики. Gates проверяют план до применения пиксельных операций.
    TDD:
      RED:
        - test_quality_gates.py::test_gate_face_dark_small_skip_correction — проваливается, если face_dark < 5% не пропускает коррекцию
        - test_quality_gates.py::test_gate_contour_inner_fallback — проваливается, если contour_inner > 30% не триггерит fallback
        - test_quality_gates.py::test_gate_skin_delta_exceeds_envelope — проваливается, если skin_delta > envelope не клипуется
        - test_quality_gates.py::test_gate_variance_loss_post_check — проваливается, если variance loss > 35% не ослабляет delta
        - test_quality_gates.py::test_gate_clipped_pct_post_check — проваливается, если clipped_pct > 5% не уменьшает rolloff
        - test_quality_gates.py::test_gate_p95_shift_post_check — проваливается, если p95 shift > 20 не ослабляет delta
        - test_quality_gates.py::test_gate_shadow_crush_post_check — проваливается, если shadow crush > 10% не отключает floor/gamma
        - test_quality_gates.py::test_gates_write_diagnostics — проваливается, если gate срабатывания не логируются в diagnostics
      GREEN:
        - реализовать pre-check gates (face_dark < 5%, contour_inner > 30%, skin_delta > envelope)
        - реализовать post-check gates (variance_loss, clipped_pct, p95_shift, shadow_crush)
        - все срабатывания пишутся в diagnostics с gate_name, step_name, original_value, adjusted_value, reason
      REFACTOR:
        - вынести пороги gates в конфиг
        - параметризовать тесты для разных профилей
    Документация:
        - CHANGELOG.md: «Feature: quality gates (pre-check and post-check)»
        - docs/reference/api.md: описать gate warnings в ответе API
        - docs/troubleshooting.md: расшифровка gate warnings

13. Сохранить batch numpy pass для зональных операций.
    TDD:
      RED:
        - test_zone_masks.py::test_batch_numpy_single_conversion — проваливается, если больше одной PIL↔numpy конверсии на группу операций
        - test_zone_masks.py::test_operation_order_invariant_for_disjoint_zones — проваливается, если порядок операций меняет результат для пересекающихся зон
      GREEN:
        - рефакторинг зональных операций в единый batch pass
        - убедиться, что resolve_zone_priority вызывается до операций
        - добавить del исходных масок после resolve
      PERF:
        - test_memory.py::test_zone_masks_memory_8k — пиковое потребление ≤ 800 MB на 8K
      REFACTOR:
        - проверить performance на большом изображении (нет кратного регресса)
        - оптимизировать порядок операций для cache locality
    Документация:
        - CHANGELOG.md: «Refactor: batch numpy pass for zonal operations»
        - docs/zones.md: описать порядок batch pass

14. Заменить global levels на skin-only bounded correction.
    TDD:
      RED:
        - test_zonal_correction.py::test_skin_only_delta_does_not_affect_clothes — проваливается, если чёрная одежда светлеет из-за лица
        - test_zonal_correction.py::test_skin_only_delta_does_not_affect_hair — проваливается, если волосы становятся серыми
        - test_zonal_correction.py::test_skin_delta_bounded_by_envelope — проваливается, если delta превышает safety envelope
        - test_zonal_correction.py::test_face_dark_small_pct_skips_correction — проваливается, если face_dark < 5% получает полную коррекцию
        - test_zonal_correction.py::test_delta_zero_when_in_target_range — проваливается, если median в target_range всё равно корректируется
      GREEN:
        - заменить arr * factor на двустороннюю формулу с target_delta
        - применять delta только к face_skin с весом от яркости
        - ослаблять face_dark correction при < 5% от face_mask
      REFACTOR:
        - параметризовать target range через конфиг
        - убедиться, что safety envelope ограничивает max_delta
    Документация:
        - CHANGELOG.md: «Refactor: global levels replaced by skin-only bounded correction»
        - README.md: обновить описание Levels
        - docs/zones.md: добавить формулу bounded delta

15. Ввести единый `soft_rolloff_masked()`.
    TDD:
      RED:
        - test_soft_rolloff.py::test_soft_rolloff_masked_compresses_highlights — проваливается, если значения выше knee не сжимаются
        - test_soft_rolloff.py::test_soft_rolloff_no_plateau — провалируется, если hard plateau появляется на ceiling
        - test_soft_rolloff.py::test_soft_rolloff_mask_applies_only_to_mask — проваливается, если пиксели вне маски изменяются
        - test_soft_rolloff.py::test_compression_from_config_not_hardcoded — проваливается, если compression хардкод вместо конфига
        - test_soft_rolloff.py::test_rolloff_vs_ceiling_precedence — проваливается, если rolloff не заменяет hard ceiling
      GREEN:
        - реализовать soft_rolloff_masked(arr, mask, knee, ceiling, compression)
        - заменить все локальные np.minimum() и np.clip() на вызовы helper
        - вынести compression в PipelinePlan / конфиг
      REFACTOR:
        - убрать дублирование ceiling-логики из levels.py и pipeline.py
        - параметризовать compression (заменить 0.50/0.35)
    Документация:
        - CHANGELOG.md: «Feature: unified soft_rolloff_masked helper replaces scattered ceiling logic»
        - docs/zones.md: добавить формулу rolloff и описание compression
        - config.yaml: добавить параметр compression

16. Финальная валидация preview/export consistency на всей системе после всех
     архитектурных изменений.
    TDD:
      RED:
        - test_preview_export_consistency.py::test_preview_export_zones_consistent — проваливается, если зоны расходятся > 5% площади
        - test_preview_export_consistency.py::test_face_oval_passed_via_context — проваливается, если face_oval не передаётся через PipelineContext
        - test_preview_export_consistency.py::test_no_redetection_in_export — проваливается, если export детектирует face_oval заново
        - test_preview_export_consistency.py::test_consistency_mismatch_warning — проваливается, если расхождение овала > 2% не генерирует warning
        - test_preview_export_consistency.py::test_thresholds_same_preview_export — проваливается, если пороги пересчитываются для preview
      GREEN:
        - реализовать PipelineContext с нормализованным face_oval
        - запретить повторную детекцию в export
        - добавить consistency_mismatch warning в diagnostics
      REFACTOR:
        - проверить все шаги, меняющие маски/параметры, на consistency
        - параметризовать допуск 5% площади
    Документация:
        - CHANGELOG.md: «Feature: preview/export consistency validation»
        - docs/architecture/pipeline.md: обновить схему preview/export flow

17. Проверить 1-bit dithering после zonal changes.
    TDD:
      RED:
        - test_dither_regression.py::test_dither_curated_set_no_new_artifacts — проваливается, если dither на curated set отличается от эталона
        - test_dither_regression.py::test_dither_preview_available — проваливается, если нет dither preview для 1bit режима
        - test_dither_regression.py::test_curated_set_has_fixtures — проваливается, если curated set < 5 изображений
      GREEN:
        - создать curated sample set (5-10 изображений в fixtures)
        - реализовать dither regression test на curated set
        - добавить dither preview в diagnostic profile
      REFACTOR:
        - хранить эталоны в репозитории, обновлять вручную при осознанном изменении
        - CI запускает dither regression на каждом PR
    Документация:
        - CHANGELOG.md: «Feature: 1-bit dither regression testing on curated set»
        - docs/troubleshooting.md: диагностика 1-bit dither артефактов

18. Разнести pipeline на сегментацию, анализ, коррекцию и экспорт.
    TDD:
      RED:
        - test_pipeline_plan.py::test_new_structure_imports_work — проваливается, если импорты из новой структуры не работают
        - test_pipeline_plan.py::test_old_imports_reexported — проваливается, если старые пути импортов не re-export
        - test_pipeline.py::test_pipeline_integration_after_restructure — проваливается, если полный пайплайн не работает после реструктуризации
        - test_pipeline_plan.py::test_pipeline_plan_schema_serializable — проваливается, если PipelinePlanSchema не сериализуется
        - test_pipeline_plan.py::test_validated_plan_schema_serializable — провалируется, если ValidatedPlanSchema не сериализуется
      GREEN:
        - создать директории segmentation/, analysis/, correction/, export/
        - перенести файлы в новую структуру
        - добавить re-export из старых путей (переходный период 6 месяцев)
        - добавить PipelinePlanSchema и ValidatedPlanSchema для API
      REFACTOR:
        - pipeline.py оркестрирует шаги, не содержит тональную логику
        - проверить, что все существующие тесты проходят
        - добавить deprecation warning для старых путей импортов
    Документация:
        - CHANGELOG.md: «Refactor: pipeline restructured into segmentation/analysis/correction/export»
        - README.md: обновить структуру проекта
        - docs/architecture/pipeline.md: обновить архитектурную диаграмму
        - docs/reference/api.md: описать PipelinePlanSchema и ValidatedPlanSchema

## Главный критерий успеха

Пайплайн должен отвечать на вопрос: "что именно было проблемой и какая зона
была изменена?"

Если ответ звучит как "мы подняли весь субъект, потому что лицо было темнее
target", это старая логика. Новая логика должна звучать так:

"Кожа лица была на 12 уровней ниже цели, поднята только skin-зона на 8 уровней.
Волосы, одежда и контур не изменялись. Света сжаты soft rolloff без hard clip."
