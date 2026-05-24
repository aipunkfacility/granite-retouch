# Troubleshooting — Расшифровка diagnostics warnings

## Hair anomaly

**`hair_mask anomaly: hair_ratio=X.XX > 0.50`**

Hair-зона занимает более 50% от маски субъекта. Возможные причины:
- Овал лица слишком маленький — hair-зона захватывает большую часть субъекта
- AI-ретушь создала нестандартную композицию (крупный план головы без плеч)

**Действие:** Проверить и скорректировать овал лица в UI.

---

**`hair_mask anomaly: hair_ratio=X.XX < 0.02`**

Hair-зона подозрительно мала. Возможные причины:
- Овал лица слишком большой — захватывает всю голову
- Субъект без волос (лысый, короткая стрижка)

**Действие:** Если у субъекта есть волосы — уменьшить овал лица. Если лысый — warning можно игнорировать.

---

## Soft knee inactive

**`soft_knee_inactive`**

Soft knee (rolloff) не применяется — все пиксели ниже knee. Это нормально для тёмных портретов.

**Действие:** Не требуется. Информационное сообщение.

---

## Quality gate warnings

Всего 7 quality gates: 2 pre-check (до обработки) + 5 post-check (после обработки).

### `face_dark_small`

**`face_dark X.X% < 5.0% — correction skipped`**

Тёмных пикселей в зоне лица менее 5%. Face dark correction пропущена.

**Причины:**
- Лицо равномерно освещено
- Адаптивный skin threshold слишком низкий

**Действие:** Не требуется — это безопасный fallback.

---

### `contour_inner_quality`

**`contour_inner X.X% > 30.0% — morphological fallback`**

Внутренний контур занимает более 30% субъекта — gradient mask некачественная.

**Причины:**
- Хромакей с пропусками
- Неровный край при удалении фона

**Действие:** Проверить качество хромакея. Fallback на morphological contour безопасен.

---

### `skin_delta_envelope` (Safety Envelope — не gate)

**`skin_delta X.X > safety envelope — clamped to ±max_delta`**

Дельта коррекции кожи превысила safety envelope из config.yaml. Это **не quality gate** — ограничение применяется через `validate_plan()` в `core/plan.py`, а не через gate-систему. Срабатывания не попадают в `gate_state`, но логируются в `validated_plan.warnings`.

**Причины:**
- Слишком агрессивная коррекция
- Некорректный threshold

**Действие:** Проверить результат — safety envelope автоматически ограничил delta. Если нужно больше коррекции — увеличить `max_delta` для зоны в config.yaml.

---

**`variance loss X.X% > 35.0% — delta weakened 50%`**

Шаг потерял более 35% variance (текстуры) в зоне face_skin.

**Причины:**
- Агрессивная коррекция яркости
- Stone gamma слишком сильный

**Действие:** Gates автоматически ослабили параметр. Проверить результат — если текстура кожи потеряна, уменьшить `stone_gamma` в config.yaml.

---

### `clipped_pct`

**`clipped X.X% > 5.0% — rolloff reduced 20%`**

Более 5% пикселей достигли white_ceiling (клиппинг).

**Причины:**
- Levels поднял яркость слишком высоко
- Rolloff compression слишком жёсткий

**Действие:** Gates автоматически увеличили `rolloff_compression`. Если пересвет остался — понизить `face_brightness_target_max`.

---

### `p95_shift`

**`p95 shift X.X > threshold — delta weakened 50%`**

P95 (95-й перцентиль яркости) face_skin сдвинулся больше допустимого порога. Порог зависит от станка: `face_skin_p95_shift_threshold` — 3.0 для laser_standard, 5.0 для impact, null (отключён) для laser_80w.

**Причины:**
- Агрессивная коррекция яркости
- Неравномерное освещение лица

**Действие:** Gates автоматически ослабили delta. Проверить результат.

---

### `shadow_crush`

**`shadow crush X.X% > 10.0% — floor/gamma skipped`**

Более 10% пикселей субъекта ушли в глубокие тени (< 5).

**Причины:**
- Shadow floor не применился
- Stone gamma затемнил тени

**Действие:** Gates пропустили floor/gamma. Проверить результат — если тени провалены, увеличить `shadow_floor`.

---

## Dither artifacts (1-bit export)

**Новые артефакты на 1-bit BMP после изменения тональной логики**

Zonal rolloff и skin-only correction меняют тональный диапазон, что влияет на паттерн Jarvis/Stucki дизеринга.

**Действие:**
1. Сравнить 8-bit preview с 1-bit результатом
2. Если артефакты на лице — уменьшить `rolloff_compression`
3. Если артефакты на волосах — проверить `hair_mask` в diagnostics
4. Обновить curated эталоны в `tests/fixtures/dither/` при осознанном изменении
