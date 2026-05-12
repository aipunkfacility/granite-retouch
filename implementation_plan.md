# granite-retouch v5.0.0 — План исправлений (на основе аудита)

> Основание: `audit-review-granite-retouch.md` (2026-05-12)  
> Цель: привести код, DEFAULTS, Pydantic, пресеты и документацию в согласованное состояние

---

## Контекст

Аудит выявил **три класса проблем**:

1. **Рассинхронизация DEFAULTS/Pydantic/config.yaml** — impact `dither_method` исправлен в YAML, но не в коде
2. **Неработающие пресеты** — `face_brightness_target` в 2–3 раза ниже физически допустимого минимума для всех 5 пресетов; `brightness` вместо `stone_gamma`
3. **Некорректный `highlight_start`** — 160 для laser_80w и impact, тогда как целевой диапазон яркости лица (190–225) находится **выше** этого порога → коррекция затухает до достижения цели

**Что НЕ делаем:** переставлять порядок `shadow_noise → shadow_floor → stone_gamma` — текущий порядок корректен и обоснован математически.

---

## Решения по открытым вопросам

- **impact dither_method** — нужен 8-bit по документации → FIX-1 оформляется как **bugfix**, не breaking change (v5.0.0, не v6.0.0)
- **Пресеты** — исходники примерно одинаковые (все из Nano Banana, синий фон), пайплайн адаптивный. Специализированные пресеты (`laser-dark-portrait`, `impact-soft`) не имеют чёткой семантики и содержат неработающие значения. **Решение: удалить**, оставить по одному каноническому пресету на тип станка.
- **`shadow_noise_min/max` после stone_gamma** — диапазон [9.7, 17.5] на выходе приемлем; не калибруем

---

## Proposed Changes

### Phase 1 — FIX-1: impact dither_method в DEFAULTS и Pydantic [DONE]

**TDD: сначала тест, потом правка.**

#### [MODIFY] [config.py](file:///f:/Dev/Projects/GRANITE/granite-retouch/retouch/config.py)

Строка 87: `"dither_method": "stucki"` → `"dither_method": "none"`

Строка 184 (Pydantic `ProcessingConfig.impact`): `dither_method="stucki"` → `dither_method="none"`

#### [MODIFY] [export.py](file:///f:/Dev/Projects/GRANITE/granite-retouch/retouch/processing/export.py)

Строка 359: обновить комментарий `# laser_80w (jarvis), impact (stucki)` → `# laser_80w (jarvis dithering), impact (8-bit grayscale, без дизеринга)`

#### [NEW] `tests/test_config_defaults_sync.py`

```python
"""TDD: DEFAULTS должны быть корректны без config.yaml."""

import os, tempfile
import pytest
from retouch.config import DEFAULTS, load_config, MACHINE_TYPES


class TestDefaultsConsistency:
    """Критические параметры DEFAULTS соответствуют документации."""

    def test_impact_dither_method_is_none(self):
        """impact использует 8-bit grayscale (256 уровней силы удара), не 1-bit."""
        assert DEFAULTS["processing"]["impact"]["dither_method"] == "none", (
            "impact.dither_method должен быть 'none' — 8-bit BMP для 256 уровней удара"
        )

    def test_laser_80w_dither_method_is_jarvis(self):
        assert DEFAULTS["processing"]["laser_80w"]["dither_method"] == "jarvis"

    def test_laser_standard_dither_method_is_none(self):
        assert DEFAULTS["processing"]["laser_standard"]["dither_method"] == "none"

    def test_defaults_without_config_yaml(self):
        """load_config() без config.yaml возвращает корректные DEFAULTS."""
        with tempfile.TemporaryDirectory() as tmp:
            orig = os.getcwd()
            os.chdir(tmp)
            try:
                cfg = load_config()
                assert cfg["processing"]["impact"]["dither_method"] == "none"
                assert cfg["processing"]["laser_80w"]["dither_method"] == "jarvis"
            finally:
                os.chdir(orig)

    def test_highlight_start_below_face_target(self):
        """highlight_start НЕ должен быть ниже face_brightness_target_min.
        Иначе коррекция затухает до достижения цели."""
        for machine in MACHINE_TYPES:
            mc = DEFAULTS["processing"][machine]
            hs = mc.get("highlight_start", 0)
            fb_min = mc.get("face_brightness_target_min", 0)
            assert hs >= fb_min - 30, (
                f"{machine}: highlight_start={hs} слишком низкий "
                f"при face_brightness_target_min={fb_min}"
            )

    def test_white_ceiling_above_face_target_max(self):
        """white_ceiling должен быть выше face_brightness_target_max."""
        for machine in MACHINE_TYPES:
            mc = DEFAULTS["processing"][machine]
            assert mc["white_ceiling"] > mc["face_brightness_target_max"], (
                f"{machine}: white_ceiling <= face_brightness_target_max"
            )
```

---

### Phase 2 — FIX-5: highlight_start в DEFAULTS, config.yaml [DONE]

**Формула:** `highlight_start = white_ceiling - 40`

| Станок | white_ceiling | highlight_start (новый) | Текущий в DEFAULTS |
|--------|:---:|:---:|:---:|
| laser_standard | 250 | 210 | 200 (близко, оставить) |
| laser_80w | 235 | **195** | 160 ❌ |
| impact | 240 | **200** | 160 ❌ |

#### [MODIFY] [config.py](file:///f:/Dev/Projects/GRANITE/granite-retouch/retouch/config.py)

- `laser_80w.highlight_start`: 160 → 195
- `impact.highlight_start`: 160 → 200
- Pydantic `ProcessingConfig.laser_80w`: `highlight_start=160` → `highlight_start=195`
- Pydantic `ProcessingConfig.impact`: `highlight_start=160` → `highlight_start=200`

#### [MODIFY] [config.yaml](file:///f:/Dev/Projects/GRANITE/granite-retouch/config.yaml)

Обновить `highlight_start` для laser_80w и impact. Тест из Phase 1 (`test_highlight_start_below_face_target`) упадёт на DEFAULTS пока не исправлено.

#### Документация

#### [MODIFY] [reference/config.md](file:///f:/Dev/Projects/GRANITE/granite-retouch/docs/reference/config.md)

В секциях `laser_80w` и `impact` обновить Default и добавить формулу:
```
highlight_start = white_ceiling - 40  (буферная зона 40 ед. перед жёстким потолком)
```

---

### Phase 3 — FIX-2+3 (объединённый): Упрощение пресетов [DONE]

**Решение:** удалить `laser-dark-portrait` и `impact-soft` (неизвестная семантика, неработающие значения). Оставить 3 канонических пресета — по одному на тип станка. Каждый явно дублирует DEFAULTS + содержит `description`.

**TDD: сначала тесты.**

#### [NEW] `tests/test_presets_validation.py`

```python
"""TDD: пресеты должны содержать физически корректные параметры."""

import pytest
import yaml
from pathlib import Path
from retouch.config import DEFAULTS, MACHINE_TYPES, deep_merge, _migrate_face_target

PRESETS_DIR = Path(__file__).parent.parent / "presets"
PRESET_FILES = list(PRESETS_DIR.glob("*.yaml"))


@pytest.mark.parametrize("preset_path", PRESET_FILES, ids=lambda p: p.stem)
class TestPresetPhysicalConstraints:

    def _load_merged(self, preset_path):
        """Загрузить пресет поверх DEFAULTS (как делает реальный пайплайн)."""
        with open(preset_path) as f:
            preset = yaml.safe_load(f)
        merged = deep_merge(DEFAULTS, preset)
        return _migrate_face_target(merged)

    def test_no_brightness_key(self, preset_path):
        """Пресеты не должны содержать устаревший ключ 'brightness'."""
        with open(preset_path) as f:
            preset = yaml.safe_load(f)
        for machine in MACHINE_TYPES:
            mc = preset.get("processing", {}).get(machine, {})
            assert "brightness" not in mc, (
                f"{preset_path.name}: найден устаревший ключ 'brightness' "
                f"в {machine}. Используйте 'stone_gamma'."
            )

    def test_face_brightness_in_physical_range(self, preset_path):
        """face_brightness_target должен быть в допустимом физическом диапазоне."""
        PHYSICAL_RANGES = {
            "laser_standard": (200, 255),
            "laser_80w": (170, 235),
            "impact": (180, 240),
        }
        cfg = self._load_merged(preset_path)
        for machine, (lo, hi) in PHYSICAL_RANGES.items():
            mc = cfg["processing"].get(machine, {})
            if not mc:
                continue
            fb_min = mc.get("face_brightness_target_min", 0)
            fb_max = mc.get("face_brightness_target_max", 0)
            assert fb_min >= lo, (
                f"{preset_path.name}/{machine}: face_brightness_target_min={fb_min} "
                f"ниже физического минимума {lo}"
            )
            assert fb_max <= hi, (
                f"{preset_path.name}/{machine}: face_brightness_target_max={fb_max} "
                f"выше физического максимума {hi}"
            )

    def test_dither_method_explicit(self, preset_path):
        """impact-пресеты должны явно задавать dither_method=none."""
        with open(preset_path) as f:
            preset = yaml.safe_load(f)
        impact = preset.get("processing", {}).get("impact", {})
        if impact:  # только если пресет затрагивает impact
            assert "dither_method" in impact, (
                f"{preset_path.name}: impact-пресет должен явно содержать dither_method"
            )
            assert impact["dither_method"] == "none"

    def test_stone_gamma_range(self, preset_path):
        """stone_gamma должен быть в допустимом диапазоне [0.70, 1.10]."""
        with open(preset_path) as f:
            preset = yaml.safe_load(f)
        for machine in MACHINE_TYPES:
            mc = preset.get("processing", {}).get(machine, {})
            if "stone_gamma" in mc:
                gamma = mc["stone_gamma"]
                assert 0.70 <= gamma <= 1.10, (
                    f"{preset_path.name}/{machine}: stone_gamma={gamma} вне диапазона [0.70, 1.10]"
                )

    def test_critical_params_present(self, preset_path):
        """Пресеты должны явно содержать критические параметры."""
        CRITICAL = {
            "laser_standard": ["white_ceiling", "dither_method"],
            "laser_80w": ["white_ceiling", "dither_method"],
            "impact": ["white_ceiling", "dither_method", "shadow_floor"],
        }
        with open(preset_path) as f:
            preset = yaml.safe_load(f)
        for machine, required_keys in CRITICAL.items():
            mc = preset.get("processing", {}).get(machine, {})
            if not mc:
                continue
            for key in required_keys:
                assert key in mc, (
                    f"{preset_path.name}/{machine}: отсутствует критический параметр '{key}'"
                )
```

#### Обновление файлов пресетов

**Таблица новых значений:**

**Оставляем 3 пресета, удаляем 2:**

| Пресет | Действие | Обоснование |
|--------|----------|-------------|
| `laser-default.yaml` | Переписать | Канонический для laser_standard = зеркало DEFAULTS |
| `laser-80w-default.yaml` | Переписать | Канонический для laser_80w = зеркало DEFAULTS |
| `impact-default.yaml` | Переписать | Канонический для impact = зеркало DEFAULTS |
| `laser-dark-portrait.yaml` | **Удалить** | Нет чёткой семантики; адаптивный пайплайн справляется |
| `impact-soft.yaml` | **Удалить** | Нет чёткой семантики; face_brightness_target физически некорректен |

**Структура нового канонического пресета (пример `impact-default.yaml`):**

```yaml
# Канонический пресет для ударной гравировки (impact)
# Явно дублирует DEFAULTS — для прозрачности и защиты от случайных изменений DEFAULTS
description: "Стандартные параметры для ударного станка (Sauno, Zubr, Mirtels). \
  Пиксель-точка — игла бьёт с силой пропорционально яркости (256 уровней)."

processing:
  impact:
    stone_gamma: 0.90
    face_brightness_target_min: 200
    face_brightness_target_max: 225
    white_ceiling: 240
    highlight_start: 200
    shadow_floor: 8
    shadow_noise_min: 5
    shadow_noise_max: 15
    shadow_noise_threshold: 30
    dither_method: none      # 8-bit grayscale: 256 уровней силы удара
    glow_size_min: 10
    glow_size_max: 25
    glow_opacity_min: 60
    glow_opacity_max: 80
    glow_style: outer

vignette:
  vertical_offset: 0.10
  vertical_diameter: 0.50
  blur_radius: 60
  headroom: 0.60
  horizontal_oversize: 0.20
```

#### [DELETE] [laser-dark-portrait.yaml](file:///f:/Dev/Projects/GRANITE/granite-retouch/presets/laser-dark-portrait.yaml)
#### [DELETE] [impact-soft.yaml](file:///f:/Dev/Projects/GRANITE/granite-retouch/presets/impact-soft.yaml)
#### [MODIFY] [laser-default.yaml](file:///f:/Dev/Projects/GRANITE/granite-retouch/presets/laser-default.yaml)
#### [MODIFY] [laser-80w-default.yaml](file:///f:/Dev/Projects/GRANITE/granite-retouch/presets/laser-80w-default.yaml)
#### [MODIFY] [impact-default.yaml](file:///f:/Dev/Projects/GRANITE/granite-retouch/presets/impact-default.yaml)

#### Документация

#### [MODIFY] [reference/config.md](file:///f:/Dev/Projects/GRANITE/granite-retouch/docs/reference/config.md)

Добавить секцию «Пресеты» с таблицей и описанием каждого.

---

### Phase 4 — shadow_noise: TDD на инварианты маски и диапазон [DONE]

**Не меняем порядок шагов.** Только улучшаем тесты.

#### [MODIFY] `tests/test_bugfixes_a.py`

Заменить хрупкий assert на параметризованный тест + добавить проверку маски:

```python
import numpy as np
import pytest
from PIL import Image
from retouch.processing.shadow_noise import add_shadow_noise


@pytest.mark.parametrize("noise_min,noise_max,shadow_floor,exp_min,exp_max", [
    (5, 15, 8,  8, 15),   # impact defaults: effective_min=max(5,8)=8
    (5, 15, 0,  5, 15),   # без floor
    (10, 20, 8, 10, 20),  # расширенный диапазон
    (5, 15, 20, 20, 15),  # floor > noise_max → шум не применяется (return img)
])
def test_shadow_noise_range(noise_min, noise_max, shadow_floor, exp_min, exp_max):
    img = Image.new("L", (50, 50), 0)
    mask = Image.new("L", (50, 50), 255)
    result = add_shadow_noise(
        img, mask,
        noise_min=noise_min, noise_max=noise_max,
        shadow_threshold=30, shadow_floor=shadow_floor,
    )
    if shadow_floor >= noise_max:
        # Шум не применяется — изображение не изменено
        assert np.array_equal(np.array(result), np.array(img))
        return
    arr = np.array(result)
    dark = arr[arr < 30]
    assert len(dark) > 0
    assert int(dark.min()) >= exp_min
    assert int(dark.max()) <= exp_max


def test_shadow_noise_mask_protection():
    """Пиксели ВНЕ маски не должны изменяться (фон остаётся чёрным)."""
    img = Image.new("L", (100, 100), 0)
    # Только левая половина — субъект
    mask = Image.new("L", (100, 100), 0)
    import PIL.ImageDraw as ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.rectangle([0, 0, 49, 99], fill=255)

    result = add_shadow_noise(img, mask, noise_min=5, noise_max=15,
                              shadow_threshold=30, shadow_floor=0)
    arr = np.array(result)

    # Правая половина (вне маски) — должна остаться 0
    right_half = arr[:, 50:]
    assert (right_half == 0).all(), "Фон (вне маски) изменён — нарушена маска субъекта"

    # Левая половина (субъект) — должна получить шум
    left_half = arr[:, :50]
    assert (left_half > 0).any(), "Субъект не получил шум"
```

---

### Phase 5 — FIX-7: laser_80w glow остаётся фиксированным [DONE]

**Действие:** не менять `glow.py` — фиксированный midpoint для laser_80w корректен (D.1).

**Документация:**

#### [MODIFY] [architecture/pipeline.md](file:///f:/Dev/Projects/GRANITE/granite-retouch/docs/architecture/pipeline.md)

В секции «Glow (шаг 5)» добавить пояснение:
```
laser_80w: фиксированный midpoint (не адаптивный) — мощный лазер сам создаёт 
контраст, адаптивность не нужна и нарушила бы preview-export consistency (D.1).
```

---

### Phase 6 — Документация: итоговый прогон [DONE]

#### [MODIFY] [docs/reference/config.md](file:///f:/Dev/Projects/GRANITE/granite-retouch/docs/reference/config.md)

- Таблица пресетов с `description`
- Формула `highlight_start = white_ceiling - 40`
- Обновить Default для `laser_80w.highlight_start` (160→195) и `impact.highlight_start` (160→200)
- Явно указать что `brightness` — deprecated, использовать `stone_gamma`

#### [MODIFY] [docs/guides/style-guide-impact.md](file:///f:/Dev/Projects/GRANITE/granite-retouch/docs/guides/style-guide-impact.md)

Добавить секцию «Параметры пайплайна»:
- Целевой диапазон яркости: 200–225
- Почему shadow_noise нужен: физика ударной гравировки
- Почему highlight_start = 200: буферная зона перед white_ceiling=240

#### [MODIFY] [docs/guides/style-guide-laser-80w.md](file:///f:/Dev/Projects/GRANITE/granite-retouch/docs/guides/style-guide-laser-80w.md)

Аналогично: highlight_start=195, white_ceiling=235.

#### [MODIFY] [CHANGELOG.md](file:///f:/Dev/Projects/GRANITE/granite-retouch/CHANGELOG.md)

```markdown
## [5.0.0] — 2026-05-XX

### Fixed
- DEFAULTS и Pydantic: impact.dither_method исправлен с "stucki" на "none"
  (bugfix: 8-bit grayscale BMP был всегда правильным форматом для impact)
- laser_80w и impact: highlight_start исправлен (160→195/200) — коррекция яркости
  теперь достигает целевого диапазона лица (190–225)
- Все 3 канонических пресета: face_brightness_target обновлён до физически 
  корректных значений; brightness заменён на stone_gamma

### Changed
- Пресеты: упрощены до 3 канонических (по одному на тип станка).
  Удалены laser-dark-portrait, impact-soft — неопределённая семантика, 
  адаптивный пайплайн обрабатывает типичные портреты без них
- Пресеты: каждый теперь явно содержит все критические параметры 
  (white_ceiling, dither_method, shadow_floor, glow_*) — самодокументируемые
- Пресеты: добавлен ключ description

### Deprecated
- Ключ `brightness` в пресетах и config.yaml — будет удалён в v6.0.0.
  Используйте `stone_gamma` (1/brightness).
```

---

### Phase 7 — Финальная проверка [DONE]

```bash
# Тесты (должны пройти все — включая новые из Phase 1-4)
make test

# Backend API (пресеты грузятся через /presets)
pytest retouch_ui/backend/tests/ -v

# Проверка что нет brightness в пресетах
grep -r "brightness:" presets/ && echo "FAIL" || echo "OK"

# Smoke-test пайплайна на синтетическом изображении
uv run python -m retouch process -i tests/fixtures/sample_blue_bg.png \
  -o /tmp/test_impact.bmp -m impact
```

---

## Verification Plan

### Automated Tests

| Тест | Что проверяет | Phase |
|------|---------------|-------|
| `test_config_defaults_sync.py` | DEFAULTS без config.yaml корректны | 1 |
| `test_config_defaults_sync.py::test_highlight_start_below_face_target` | DEFAULTS highlight_start ≥ face_target_min - 30 | 2 |
| `test_presets_validation.py` | Пресеты: физические диапазоны, no brightness, dither_method явный | 3 |
| `test_bugfixes_a.py::test_shadow_noise_range` | Диапазон шума параметризован | 4 |
| `test_bugfixes_a.py::test_shadow_noise_mask_protection` | Фон не изменяется | 4 |
| `make test` (все 365+ тестов) | Нет регрессии | 7 |

### Порядок выполнения с учётом зависимостей

```
Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5  →  Phase 6  →  Phase 7
(FIX-1)    (FIX-5)    (FIX-2+3)   (tests)    (FIX-7 noop)  (docs)    (verify)
```

> Phases 1–4 содержат TDD: сначала пишем тест (он падает), потом правим код/данные (тест зеленеет).

### Manual Verification

- Проверить что `retouch_ui/backend/tests/test_presets_api.py` проходит после обновления пресетов
- Убедиться что `validate_config()` не возвращает warnings для всех 5 пресетов после merge с DEFAULTS
