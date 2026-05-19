# Changelog

Все заметные изменения в проекте granite-retouch фиксируются в этом файле.

## [6.4.0] - 2026-05-20

### Рефакторинг пайплайна (pipeline-refactor-plan)

Модульная архитектура обработки: 5 новых модулей, zone-based метрики, quality gates, bounded delta для levels.

### ✨ Новые модули

- **`zones.py`** — `ZoneMasks`, `build_zone_masks()`, `resolve_zone_priority()` — зональное разделение (face_skin, face_dark, hair, clothes, background) с гарантией дизъюнктности масок
- **`plan.py`** — `PipelinePlan`, `SafetyEnvelope`, `ValidatedPlan`, `validate_plan()` — структурированный план обработки с лимитами коррекций
- **`metrics.py`** — `ZoneMetrics`, `StepMetricsRecord`, `compute_zone_metrics()` — метрики по зонам после каждого шага
- **`rolloff.py`** — `soft_rolloff_masked()` — унифицированный soft knee для highlights, заменяет inline `np.clip`
- **`gates.py`** — 7 quality gates (3 pre-check, 4 post-check) — `GateResult` с severity и message

### 🔧 Изменения

- **`levels.py` переписан**: `factor` заменён на двустороннюю bounded delta формулу (`delta = target - median`, `factor = 1 + delta/median`)
- **Shadow floor для laser**: ограничен `face_mask` — не применяется к hair/clothes (fix: ранее применялся ко всему изображению)
- **`unsharp.py`**: удалён hard clamp до `white_ceiling` (теперь через `soft_rolloff_masked`)
- **`pipeline.py`**: добавлены поля `profile`, `step_metrics`, `plan`, `validated_plan`, `zone_masks`, `gate_state`
- **Hair diagnostics**: `hair_mask`, `hair_anomaly`, `hair_ratio` в `PipelineContext` и `PipelineResult` — автоматическое обнаружение аномалий hair-зоны
- **`export_defaults.py`**: добавлен `--check` режим для CI
- **`Makefile`**: добавлен `check-defaults-sync` target

### 📚 Документация

- **`pipeline.md`**: обновлены секции Levels, Shadow Floor, White Ceiling, PipelineContext, PipelineResult
- **Новая секция**: «Новые модули обработки (v6.4)» — описание zones, plan, metrics, rolloff, gates

### 🧪 Тестирование

- 463 passed, 14 pre-existing failures (не связаны с рефакторингом)
- 81+ новых тестов для модулей zones, plan, metrics, rolloff, gates

## [6.3.0] - 2026-05-15

### UI-рефакторинг (audit-ui-v7)

Исправлены 9 ошибок компиляции, 7 логических проблем, 14 дополнительных проблем.

### UI/UX Audit Fixes

#### Fixed
- Тёмная палитра: `machine-theme.ts`, `MachineSelector`, `MaterialSelector`, `App.tsx` — заменены светлые классы `*-50`/`*-200` на `accent-*/N` с opacity
- Эмодзи → Remix Icon: `💡` → `ri-lightbulb-line`, `⚠️` → `ri-alert-line`/`ri-error-warning-line`, `🚫` → `ri-forbid-line`, `ℹ️` → `ri-information-line`
- Контраст `text-muted`: `#666666` → `#888888` (4.6:1 — WCAG AA)
- Единый border-radius: `rounded`/`rounded-md` → `rounded-lg` (8px)

#### Added
- JetBrains Mono (weight 400) — `--font-mono` для моноширинного текста
- Focus-visible стили — `outline: 2px solid var(--color-border-focus)` для кнопок, ссылок, инпутов
- ARIA-атрибуты — `aria-expanded`, `aria-haspopup`, `aria-pressed`, `aria-selected`, `aria-current`, `role="listbox"`/`option`/`tablist`/`tab`/`tabpanel`
- Клавиатурная навигация в MachineSelector — ArrowDown/Up, Enter, Escape
- Диалоги подтверждения на «Сброс» и «Удалить пресет» (`window.confirm`)
- Единый toast-провайдер (`components/toast-provider.tsx`) — `showToast(msg, opts?)` через контекст
- Кастомный Slider (`components/slider.tsx`) — заполнение трека, иконка сброса `ri-arrow-go-back-line`, ARIA
- Визуальные индикаторы в DiagnosticsPanel — `text-accent-green`/`text-accent-orange`/`text-accent-red` для brightness delta и black_ratio
- Клиентская валидация файлов — форматы (.png/.jpg/.jpeg/.tif/.tiff/.bmp), макс. 50 MB
- Labels на face-oval handles — `<text>` SVG элементы с шрифтом JetBrains Mono
- Tooltip-описания для DiagnosticsPanel — `title` атрибуты на каждой строке
- Спиннер при загрузке изображения — `ri-loader-4-line animate-spin`
- Empty state с иконкой `ri-image-line` и подсказкой форматов
- Адаптивная высота before-after — `max-h-[min(70vh,600px)]`
- Разделитель кнопки дизеринга — `border-l border-border`

#### Removed
- `machine-switch.tsx` — заменён на `module-switch.tsx`
- Локальный toast state из `App.tsx`, `export-buttons.tsx`, `material-selector.tsx`
- Устаревший `MACHINE_COLORS` → `MACHINE_THEME`

#### Удалённые пропсы
- `presetBaseline` из `ParamsPanel`
- `machineType` из `StepSelector`

#### Изменённые сигнатуры
- `computeParamsFromTopDragShift()` — убран параметр `imageWidth`
- `selectMaterial()` — возврат `Promise<{ success: boolean; validationWarnings: string[] }>` вместо `Promise<boolean>`
- `UsePresetMaterialReturn`: +`groups`, +`presetsCache`, +`presetsLoaded`, +`presetsError`, +`materialError`, -`setMachineType`
- `MachineSelectorProps`: +`presetsCache`
- `ModuleSwitchProps`: +`presetsCache`
- `ConfigActionsProps`: +`presetsCache`
- `useConfig` return: +`error`

#### Новые файлы
- `src/lib/machine-theme.ts` — единый `MACHINE_THEME` (FIX-16)
- `src/components/error-boundary.tsx` — ErrorBoundary с UI (FIX-25)
- `vitest.config.ts` — конфигурация Vitest (FIX-0.1)
- `src/test/setup.ts` — setup с jsdom + PointerEvent mock (FIX-0.1)
- `src/test/mocks/api.ts` — моки API (FIX-0.2)

#### Удалённые вызовы fetchPresets
- `machine-selector.tsx` — теперь получает `presetsCache` через props
- `module-switch.tsx` — теперь получает `presetsCache` через props
- `config-actions.tsx` — теперь получает `presetsCache` через props

#### Новые функции и хелперы
- `getMachineParams(machineKey: MachineType)` — type-safe доступ к параметрам станка с `never` guard
- `isConfigTree(val: unknown)` — runtime guard для ConfigTree с prototype check
- `getExportMode(config, machineType)` — безопасное извлечение export_mode
- `clamp(val, min, max)` — общая утилита в `lib/utils.ts`
- `invalidateCatalogCache()` / `invalidateProfilesCache()` — инвалидация module-level кэша

#### ESLint
- `react-hooks/exhaustive-deps` = `error`

#### Прочее
- Shift-трекинг в face-oval-overlay (useEffect с keydown/keyup/blur/pointerdown)
- Side effect в material-selector перенесён из тела рендера в useEffect
- IIFE в App.tsx заменён на `pm.groups`
- Все non-null assertions (`!`) в App.tsx заменены на optional chaining/local vars
- Все `as unknown as ConfigTree` и `as ConfigTree` заменены на isConfigTree guard
- setTimeout cleanup (clearTimeout + unmount cleanup) в material-selector и App.tsx
- Удалён мёртвый код: `svgScale`, `svgRef`, мёртвый if-блок, `setMachineType`
- Дедупликация: `FaceOvalParams` → реэкспорт из types.ts, `MACHINE_COLORS` → `MACHINE_THEME`
- Silent catch заменён на error state: `materialError` в use-preset-material, `error` в use-config

## [6.2.0] - 2026-05-14

### Added
- Пресеты станков по производителю: 8 новых YAML (Mirtels, САУНО, Stanzone, STONE-ГРАФ)
- Пресет `stanzone-laser-1bit` — критичный: Stanzone лазер работает ТОЛЬКО в 1-bit
- `MATERIAL_PROFILES` (бывший `STONE_PROFILES`): step_mm_range, stone_gamma_range, shadow_floor по материалу
- `acrylic` добавлен как `material` — автопереключение в 1-bit + Jarvis (мануал Mirtels)
- `presets_catalog.py` — реестр пресетов с метаданными для UI (бренд, категория, alert)
- `apply_material_overrides()` — автокоррекция параметров при смене материала (логгинг + changes для UI)
- `validate_machine_material()` — валидация несовместимых комбинаций станок+материал
- CLI: `--preset`, `--material`, `--stone` (deprecated alias), `--list-presets`
- API: `GET /api/presets/catalog` — доступ к PRESET_CATALOG для фронтенда
- Миграция v3→v4: `stone.type` → `material` с backward compatibility

### Changed
- `stone.type` → `material`: переименование с backward compatibility (deprecated в v4, удаление в v5)
- `STONE_PROFILES` → `MATERIAL_PROFILES`: переименование, `STONE_PROFILES` = alias
- `apply_stone_overrides()` → `apply_material_overrides()`: переименование, alias сохранён
- `laser-80w-default.yaml`: добавлено предупреждение о Stanzone
- Пресет `mirtels-impact`: название «Mirtels (ударный, все модели)» — явно указывает на все модели
- `StoneConfig` Pydantic: поле `type` deprecated, добавлено `material` с acrylic
- `types.ts`: добавлен `MaterialType`, `StoneType` = deprecated alias
- `config.yaml`: `config_version: 4`, добавлен `stone.material`

### Fixed
- Stanzone лазерный модуль: теперь корректно экспортирует 1-bit BMP
- Mirtels ударный: step_mm=0.24 (105.8 dpi по мануалу) вместо 0.30
- Акрил + ударный: валидация блокирует некорректную комбинацию

## [6.1.0] - 2026-05-14

### 💥 Breaking Changes

- **export_mode: "8bit" по умолчанию** — все станки САУНО теперь экспортируют 8-bit grayscale BMP вместо 1-bit. Engrave модулирует мощность лазера по яркости пикселей (алгоритмы Р1–Р5), что невозможно при 1-bit BMP. Ключ `dither_method` заменён на `export_mode` + `dither_method_1bit`
- **laser_80w дефолты**: `stone_gamma: 0.85→1.0`, `step_mm: 0.300→0.250`, `face_brightness_target_min: 190→160`, `face_brightness_target_max: 210→180`
- **per-machine step_mm**: `step_mm` перемещён из глобальной секции `machine:` в `processing.{machine}.step_mm` (глобальный сохранён как fallback)
- **Миграция v2→v3**: `dither_method="none"` → `export_mode="8bit"`, `dither_method="jarvis"` → `export_mode="1bit", dither_method_1bit="jarvis"`. Миграция идемпотентна

### ✨ Новые возможности

- **export_mode**: новый параметр `"8bit" | "1bit"` в MachineConfig — определяет формат BMP. 8-bit grayscale по умолчанию
- **dither_method_1bit**: метод дизеринга при export_mode='1bit' (jarvis для лазеров, stucki для impact)
- **save_bmp_8bit()**: DPI в заголовке BMP из step_mm (`dpi = 25.4 / step_mm`) — Engrave предупреждает при несоответствии
- **export_result() routing**: приоритет: явный fmt > export_mode > dither_method (fallback)
- **Dither preview для всех машин**: кнопка «Просмотр дизеринга» доступна для всех станков, метод берётся из dither_method_1bit
- **_apply_dither()**: унифицированный вызов дизеринга по имени метода (jarvis/stucki)
- **Config migration v2→v3**: автомиграция dither_method→export_mode, global step_mm→per-machine, laser_80w gamma/fb перекалибровка
- **Frontend: exportMode prop** в StepSelector, export_mode ParamToggle, step_mm ParamRange в config-schema

### 🐛 Исправления

- **test_config_api.py: 403 на PUT /api/config**: `_validate_path_containment()` отклонял tmp_path (вне _PROJECT_ROOT) — добавлен monkeypatch обхода в тестах
- **Dither preview: hardcoded jarvis + laser_80w-only**: теперь читает dither_method_1bit из конфига, доступен для всех станков
- **schemas.py DitherPreviewRequest**: regex `^(laser_80w)$` → `^(laser_standard|laser_80w|impact)$`
- **_params_to_overrides()**: step_mm записывается в per-machine конфиг, а не в глобальный machine.step_mm

### 📚 Документация

- **config.md**: обновлена сводная таблица (gamma=1.0, fb=160/180, export_mode, step_mm, dither_method_1bit), секция laser_80w, секция export, секция machine
- **pipeline.md**: шаг 11 (BMP экспорт) и dither-preview обновлены для v3 export_mode
- **style-guide-laser-80w.md**: яркость лица 190–210 → 160–180
- **laser.md**: яркость laser_80w 190–210 → 160–180
- **Docstrings**: обновлены в config.py, export.py, pipeline.py, process.py, config.py router

### 🧪 Тестирование

- 482 автотестов (было 478), 0 failed
- Новые тесты: export_mode routing, DPI в BMP, миграция v2→v3, per-machine step_mm, Pydantic MachineConfig

## [6.0.0] - 2026-05-12

### Breaking Changes

- **Accent palette**: `--color-accent-blue` изменён с `#4a90d9` на `#7C8CF8` (Labradorite)
- **Status colors**: green/orange/red → Emerald/Amber/Rose
- **`legacy_step_order` убран из UI**: доступен только через config.yaml
- **`dither_upsample` удалён**: NEAREST downsample на 1-bit — no-op, параметр не давал эффекта. Функция `dither_with_upsample()` удалена из `export.py`, поле удалено из `MachineConfig`, `DEFAULTS`, `config.yaml`, пресетов и `config-defaults.json`
- **Градиентная маска хромакея**: вместо бинарного порога + OpenCV contour tracing альфа-канал вычисляется напрямую из градиента «степени синевы» (soft-step вокруг threshold). Устраняет зазубренный контур на диагоналях. `contour_smooth_epsilon` deprecated (игнорируется). Fringe removal сохранён (бинарный порог для RGB-коррекции). Ветка `if HAS_CV2:` убрана — один путь для всех окружений

### Новые возможности

- **Labradorite accent palette**: дизайн-система приведена к палитре Granite CRM. Акцентный цвет — Labradorite `#7C8CF8`, статусные — Emerald/Amber/Rose
- **Advanced Mode**: технические параметры скрыты по умолчанию, доступны по чекбоксу Advanced. Оператор видит 5-7 ключевых слайдеров вместо 12+
- **ParamToggle**: `glow_style` — сегментный контрол (Outer/Inner) вместо слайдера 0-1. Новый тип `ParamToggle` в config-schema
- **Dither preview**: предпросмотр Jarvis дизеринга для laser_80w (по кнопке «Просмотр дизеринга»). Без Numba — 30-120 сек с подтверждением оператора. Эндпоинт `POST /api/process/dither-preview`
- **Pin Face Oval**: фиксация овала лица кнопкой-пин. Ручное перемещение овала автоматически ставит Pin ON, блокируя автообновление из автодетекции. Pin OFF — овал обновляется из diagnostics
- **mask_soft_sigma / contour_smooth_epsilon**: добавлены в config-schema (Advanced). Ранее отсутствовали в UI-схеме
- **HIDDEN_PARAMS**: `legacy_step_order` полностью убран из UI (доступен только через config.yaml)
- **ADVANCED_PARAMS**: `blue_threshold`, `min_blue_ratio`, `fringe_radius`, `min_resolution`, `result_min_black_ratio`, `face_region_top`, `highlight_start`, `unsharp_threshold`, `mask_soft_sigma`, `contour_smooth_epsilon` — скрыты по умолчанию

### Документация

- **design-system.md**: переписан — тёмная тема для Retouch, Remix Icon вместо Lucide, Outfit для заголовков, разделение CRM/Retouch
- **config.md**: пометки [Advanced] / [Hidden] для параметров, `glow_style` описан как toggle
- **pipeline.md**: описание Pin-механизма и dither preview
- **webui-setup.md**: Advanced Mode, Pin Face Oval, Просмотр дизеринга

## [5.0.0] - 2026-05-12

### ✨ Новые возможности

- **Антиалиасный контур хромакея**: векторная трассировка через OpenCV (`findContours` → `approxPolyDP` → `drawContours(LINE_AA)`) вместо GaussianBlur поверх бинарной маски. Настоящий субпиксельный антиалиасинг — нет лесенки на диагоналях
- **Зависимость `opencv-python>=4.8.0`**: для векторной трассировки контура. Без cv2 — fallback на старый GaussianBlur-подход
- **Параметр `contour_smooth_epsilon`** в config.yaml (0.001–0.01, дефолт 0.002): степень сглаживания контура. 0.001 = минимальное, 0.005 = агрессивное (сглаживает пряди волос)
- **Параметр `mask_soft_sigma`** в config.yaml (0–5.0, дефолт 1.5): ширина размытия краёв subject_mask
- **`PipelineResult.face_oval`** (AUDIT-3.1): параметры овала лица передаются из preview в export без повторной детекции
- **CLI `--face-oval`**: ручное задание овала лица `CX,CY,RX,RY` (нормализованные 0–1)
- **`numba_available` в Web UI**: `PreviewDiagnostics` содержит флаг доступности Numba — при False показывается баннер «Дизеринг медленно, установите uv sync --extra fast»

### 🐛 Исправления

- **impact dither_method: stucki → none** (FIX-1): ударные станки требуют 8-bit grayscale (256 уровней силы удара), а stucki давал 1-bit — все полутона лица терялись. 8-bit BMP теперь стандарт для impact
- **laser_80w и impact: highlight_start исправлен (160→195/200)** (FIX-5): коррекция яркости теперь достигает целевого диапазона лица (190–225). Формула: `white_ceiling - 40`
- **Лесенка на контуре портрета**: `scipy.binary_dilation/erosion` с крестовым ядром → OpenCV LINE_AA с субпиксельным антиалиасингом. Старый GaussianBlur-подход давал alpha=1-2 вместо значимых 50-200
- **Утечка файлового дескриптора** (AUDIT-2.2): `Image.open()` в контекстном менеджере — файл освобождается даже при исключении
- **laser_80w: glow_size рассинхрон** (AUDIT-9.1): `config.yaml` приведён к DEFAULTS (`glow_size_min=15, glow_size_max=25`)
- **Face correction: след маски на лице**: мягкая маска (float 0-1) вместо бинарной (bool) — градиентный переход без видимого скачка яркости
- **`no_validate` не пробрасывался** (AUDIT-2.1): CLI флаг `--no-validate` теперь доходит до `process_steps()`
- **cv2 fallback warning**: если opencv-python не установлен, `_make_smooth_mask()` теперь логирует warning о возможной лесенке на контуре

### 🔧 Изменения

- **Пресеты упрощены до 3 канонических** (FIX-2+3): удалены `laser-dark-portrait` и `impact-soft` (неопределённая семантика). Оставшиеся пресеты (`laser-default`, `laser-80w-default`, `impact-default`) переписаны как явные зеркала DEFAULTS с полем `description`
- **Ключ `brightness` объявлен deprecated**: заменён на `stone_gamma` (1/brightness) во всём проекте. Автомиграция сохранена для обратной совместимости до v6.0.0
- **Web UI: Windows-фикс**: запуск через `python -m uvicorn` вместо `uv run uvicorn` (Windows теряет venv в child process)
- **Numba JIT warmup**: прогрев при старте backend (FastAPI lifespan) и CLI — первый экспорт с дизерингом без задержки
- **Deprecated reexports** (AUDIT-3.4): `_reexport_cache` заменён на `globals()` + `__getattr__` с `_DEPRECATED_REEXPORTS` dict
- **`apply_inner_glow` deprecated** (AUDIT-5.5): alias выдаёт DeprecationWarning, рекомендует `apply_glow`
- **Тесты перераспределены по модулям**: вместо `test_audit_fixes.py` — `test_pipeline.py`, `test_cli_integration.py`, `test_face_correction.py`, `test_glow.py`, `test_config.py`, `test_api.py`

### 🧪 Тестирование

- **375+ автотестов** (было 266+) + 31 backend API тест
- Новые тесты инвариантов: `test_config_defaults_sync.py`, `test_shadow_noise_invariants.py`
- Проверка реального антиалиасинга: промежуточные значения >10 на контуре (не только 1-2)

## [5.0.0] - 2026-05-08

### 💥 Breaking Changes

- **Порядок шагов пайплайна** (A.3): unsharp mask теперь ПОСЛЕ face_brightness correction. Старый порядок доступен через `legacy_step_order: true` в config.yaml для rollback без redeploy
- **Glow детерминирован** (D.1): `random.randint()` заменён на midpoint диапазона. Результат воспроизводим — preview и export дают одинаковый glow
- **Glow rename** (A.5): `apply_inner_glow()` — это теперь диспетчер `apply_glow()`, а настоящий inner glow — `apply_inner_glow_algorithm()`. Параметр `glow_style: inner | outer`
- **Модули расщеплены** (F.1): `levels.py` разделён на `levels.py`, `unsharp.py`, `face_correction.py`, `shadow_noise.py`. Backward-compatible re-exports сохранены

### ✨ Новые возможности

- **PipelineContext** (B.1): внутренняя упаковка параметров пайплайна — уменьшает количество пробрасываемых аргументов между шагами
- **ImageAnalytics dataclass** (B.3): структурированные метрики с `from_dict()`/`to_dict()`
- **Детекция зоны лица** (C.1): трёхуровневая стратегия — профиль ширины маски (85-90% покрытий) → ручной овал (FaceOvalOverlay) → mediapipe (будущее)
- **Маска лица и волос** (C.2): `generate_face_mask()`, `generate_hair_mask()` из овала
- **FaceOval UI** (E.1): интерактивный SVG-эллипс для ручной коррекции овала лица
- **Shadow Floor** (A.2): отдельный шаг для impact — `np.maximum(arr, shadow_floor)`
- **White Ceiling Clamp** (A.4): hard clamp белой точки перед виньеткой
- **Quality Metrics** (F.2): `clipped_pixels_pct`, `shadow_crush_pct`, `tonal_range_output`, `quality_warnings` в PipelineResult
- **BMP Post-Validation** (F.3): автоматическая проверка mode и size после сохранения
- **Preview Cache** (D.6): LRU-кэш с `_stable_serialize()` (float round 4 знака → SHA256)
- **TTL Cleanup** (D.5): фоновая корутина удаляет файлы старше 30 мин с учётом ref_count
- **Pydantic валидация** (D.4): `brightness=999` → 422 Validation Error
- **CLI `--overwrite`** (D.7): защита от случайной перезаписи выходного файла
- **`process_export(overwrite=)`** (D.7): программный контроль перезаписи, согласованный с CLI

### 🐛 Исправления

- **Shadow noise на фоне** (A.1): `add_shadow_noise()` добавлял шум в чёрные пиксели фона вместо субъекта — исправлено на `subject_dark = mask_bool & (arr < threshold)`
- **Shadow floor для impact** (A.2): тени уходили в 0 без восстановления — добавлен отдельный шаг `np.maximum(arr, shadow_floor)`
- **Порядок шагов** (A.3): unsharp до face_brightness → резкость смазывалась коррекцией — переставлен порядок, legacy_step_order для rollback
- **White ceiling clamp** (A.4): после shadow_noise и vignette могли появиться пиксели > white_ceiling — hard clamp перед виньеткой
- **Glow rename** (A.5): `apply_inner_glow()` делал outer glow — переименован в `apply_outer_glow()`, написан настоящий `apply_inner_glow_algorithm()`
- **Pillow DeprecationWarning**: `Image.fromarray(arr, "L")` → `Image.fromarray(arr)` в 7 processing-модулях и 13 тест-файлах (60+ вызовов)
- **Preview cache FIFO→LRU**: заменён на OrderedDict + `move_to_end()` для оптимального вытеснения
- **`_params_to_overrides()` P0**: возвращал `{}` вместо `({}, None)` — ломал распаковку кортежа
- **`test_upload_limit` P0**: использовал 2-элементные кортежи вместо 4-элементных

### 🧪 Тестирование

- **266+ автотестов** (было 132+) + 31 backend API тест
- Новые файлы: `test_bugfixes_a.py` (15), `test_architecture_b.py` (14), `test_face_region.py` (12), `test_audit_fixes.py` (7), `test_quality_f.py` (8), `test_regression_g.py` (16)
- 0 DeprecationWarnings при `-W error::DeprecationWarning:PIL`

## [3.1.0] - 2026-05-08

### 💥 Breaking Changes

- **Формат экспорта по умолчанию**: TIFF → BMP. CLI теперь сохраняет BMP вместо TIFF. Для совместимости доступен `--format tiff`.
- **Схема face_brightness_target**: формат списка `[min, max]` заменён на отдельные ключи `face_brightness_target_min` / `face_brightness_target_max`. Старый формат автоматически мигрируется при загрузке.
- **Порт Web UI**: 8001 → 8000. Vite proxy и Makefile обновлены. Если запускаете uvicorn вручную — используйте `uv run uvicorn ... --port 8000`.

### ✨ Новые возможности

- **BMP экспорт** (`retouch/processing/export.py`): 8-bit grayscale BMP для laser_standard/impact, 1-bit BMP с Floyd-Steinberg дизерингом для laser_80w
- **CLI `--format`**: новый аргумент — `bmp` (default), `bmp_1bit`, `bmp_8bit`, `png`, `tiff`
- **White ceiling**: параметр `white_ceiling` ограничивает максимальную яркость пикселей (кроме зрачков). laser_standard: 250, laser_80w: 235, impact: 240
- **Shadow noise**: `add_shadow_noise()` для impact — шум в глубоких тенях даёт игле «зацепку» (параметры `shadow_noise_min`/`shadow_noise_max`)
- **Pillow-fallback warning**: если numpy недоступен, `check_face_brightness()` логирует предупреждение о том, что масочная защита отключена

### 🐛 Исправления

- **Double brightening**: исправлен баг двойного усиления яркости (Levels ×1.35 + Face Correction ×1.20) — теперь адаптивный фактор + face correction работают корректно
- **Laser 80W face targets**: восстановлены экспертные значения 190–210 (commit b183522 ошибочно снизил до 150–170)
- **Web UI port mismatch**: Vite proxy указывал на 8001, uvicorn слушал 8000 → таймаут загрузки 30 сек

### 📚 Документация

- Обновлены все ссылки TIFF → BMP в: README, getting-started, cli.md, config.md, pipeline.md, overview.md, vignette.md
- Добавлены новые параметры: white_ceiling, shadow_noise_min/max, face_brightness_target_min/max
- webui-setup.md: порт 8000, troubleshooting «Загрузка превышена»
- BACKLOG-006: shadow_noise отмечен как реализованный

## [4.0.0] - 2026-05-07

### 💥 Breaking Changes

- **`machine_type` расширение**: значение `"laser"` заменено на `"laser_standard"`. Старое значение `"laser"` вызывает ошибку валидации в schema.json. Если в order.json указан `"machine_type": "laser"` — замените на `"laser_standard"`.
- **`config.yaml` ключи**: секция `processing.laser:` переименована в `processing.laser_standard:`. Добавлена секция `processing.laser_80w:`.

### ✨ Новые возможности

- **Пресет laser-80w.md**: новый стиль для мощных лазеров (60-80W+) — medium-key, тёмные волосы, сохранённые морщины, потолок яркости 235
- **26 промпт-правок** (B1–B16, C-L0/L2/L3, C-I1/I2/I3): уточнение Goal, clothing blowout, серебряный тон, скульптурный объём волос, «лучше темнее»
- **Модуль преданализа** (`retouch/processing/analysis.py`): 13 метрик входного изображения для адаптивных доработок пайплайна
- **Адаптивный Levels** (P2): фактор яркости вычисляется из analytics вместо фиксированного 1.18, защита от клиппинга
- **Адаптивный Glow** (P3): параметры glow рассчитываются из analytics (subject_separation, tonal_range)
- **Адаптивный Unsharp** (P5): percent вычисляется из analytics (input_class, tonal_range)
- **Целевые значения по пресету** (P4): config.yaml содержит 3 секции — laser_standard, laser_80w, impact
- **Масочная защита** (P6): `apply_levels()` и `apply_unsharp_mask()` принимают `subject_mask`, коррекция только внутри маски
- **P6.4 Pillow-fallback mask**: `check_face_brightness()` Pillow-ветка теперь ограничивает коррекцию внутри маски субъекта через numpy пост-обработку
- **PipelineResult.analytics**: dict с метриками преданализа доступен после обработки
- **34 новых TDD-теста** для этапов 5–11 дев-плана

### 🐛 Исправления

- **BUG-C**: impact face_brightness_target поднят с [185, 210] до [200, 225] — устраняет плоские лица на impact-гравировке
- **CLI docstring**: обновлён с `-m laser_standard` вместо устаревшего `-m laser`
- **Промпты**: убрано дублирование фраз про «flat hair» в laser.md §2 и impact.md §2

## [3.0.0] - 2026-05-05

### 💥 Breaking Changes

- **`check_face_brightness()` return**: функция теперь возвращает кортеж `(img, before, after, factor)` вместо одного значения `Image`. Первым элементом — скорректированное изображение, затем яркость до, яркость после и множитель коррекции. Код, ожидавший только `Image`, нужно обновить: `result, before, after, factor = check_face_brightness(...)`.
- **`load_config()` deep_merge**: конфиг теперь загружается с `deep_merge` — пользовательский конфиг мержится с defaults рекурсивно, а не заменяет целые секции. Если вы полагались на полную замену секции — используйте пустые значения явно.
- **`process()` wrapper**: функция `process()` теперь обёрнута в `process_steps()` / `process_preview()` / `process_export()`. Старый вызов `process()` с полным набором аргументов может вести себя иначе — используйте новые функции.

### ✨ Новые возможности

- **Web UI**: интерактивный интерфейс для настройки параметров ретуши с живым предпросмотром
  - FastAPI backend (`retouch_ui/backend/`) с роутерами: upload, process/preview, process/export, config, presets
  - React + Vite frontend (`retouch_ui/frontend/`) со слайдерами, компаратором до/после, диагностикой
  - Запуск: `make ui` (dev) или `make ui-prod` (production, один процесс)
  - Production: FastAPI раздаёт статику через `StaticFiles` — достаточно одного uvicorn
- **`PipelineResult`**: новый класс результата обработки с промежуточными изображениями, диагностикой и `release_intermediates()`
- **`process_steps()` / `process_preview()` / `process_export()`**: специализированные функции вместо одной `process()`
- **Пресеты**: директория `presets/` с YAML-файлами (laser-default, laser-dark-portrait, impact-default, impact-soft)
- **Pydantic-модели**: валидация запросов/ответов backend через Pydantic (UploadResponse, PreviewRequest, ExportRequest, HealthResponse)
- **Параметры `face_region_top` и `highlight_start`**: контроль области замера яркости и защита от пересвета

### 🐛 Исправления

- **Fringe test**: исправлен тест fringe removal — корректная проверка синего канала в переходной зоне
- **File descriptor leak**: временные файлы экспорта удаляются через `BackgroundTask` после отдачи клиенту
- **Config overwrite**: `load_config()` с `deep_merge` — пользовательский конфиг больше не затирает defaults неявно

## [2.6.0] - 2026-05-04

### 🧪 Тестирование (Фаза 7)

- **`tests/conftest.py`:** фикстуры для синтетических изображений с хромакеем
  - `make_chromakey_image()` — RGBA с синим фоном и эллипсом-субъектом
  - `make_no_chromakey_image()` — без хромакея (негативные тесты)
  - `make_dark_blue_clothing_image()` — тёмно-синяя одежда (граничный кейс)
  - Фикстуры: `chromakey_png`, `small_chromakey_png`, `no_chromakey_png`, `valid_order_json`, etc.
- **`tests/test_chromakey.py`** (7 тестов): удаление синего фона, сохранение субъекта, fringe removal, тёмно-синяя одежда, режимы RGBA/L
- **`tests/test_glow.py`** (6 тестов): laser/impact glow размеры, яркость контура, случайный glow в диапазоне, минимальная opacity
- **`tests/test_levels.py`** (10 тестов): brightness, unsharp mask, curves-коррекция (тени/света), сжатие маски, контроль яркости лица
- **`tests/test_vignette.py`** (7 тестов): RGB-результат, чёрные углы, headroom, масштабирование, плавная маска
- **`tests/test_validation.py`** (16 тестов): валидация изображения, хромакей, чёрный фон, order.json (валидные/невалидные, CRM, формат ID)
- **`tests/test_config.py`** (10 тестов): DEFAULTS-структура, диапазоны glow/brightness, загрузка из файла, fallback
- **`tests/test_pipeline.py`** (8 тестов): интеграция — laser/impact полный пайплайн, чёрный фон, отсутствие пересвета, no-validate режим

**Итого: 72 теста, все проходят.**

## [2.5.0] - 2026-05-04

### 📚 Модуляризация документации

- **`docs/`** — единая директория документации (вместо разброса по 6 местам)
  - `docs/index.md` — карта документации
  - `docs/getting-started.md` — быстрый старт за 5 шагов (заменяет workflow.md)
  - `docs/reference/cli.md` — полный справочник CLI
  - `docs/reference/config.md` — все параметры config.yaml с диапазонами
  - `docs/reference/order-schema.md` — поля order.json
  - `docs/guides/vignette.md` — обновлено (ссылки на `python -m retouch process`)
  - `docs/guides/style-guide-laser.md` — стиль лазерной генерации
  - `docs/guides/style-guide-impact.md` — **НОВЫЙ**: стиль ударной генерации
  - `docs/guides/nano-banana.md` — работа с Nano Banana
  - `docs/architecture/overview.md` — структура проекта, потоки данных
  - `docs/architecture/pipeline.md` — пайплайн обработки + диагностика проблем
  - `docs/integration/crm.md` — связь с granite-crm
- **AGENTS.md** → сокращён до навигатора (~80 строк вместо 354)
- **README.md** → обновлён: CLI-команды, ссылки на docs/
- **workflow.md** → редирект на docs/getting-started.md
- **BACKLOG.md** → версия исправлена на 2.4.0
- **retouch-prompter/SKILL.md** → исправлена ссылка: `prompt_blocks/machine/` → `prompt_blocks/`
- Стиль переименован: «Memorial High-End Airbrush» → «Granite High-End Airbrush»

## [2.4.0] - 2026-05-04

### 🔗 Интеграция с granite-crm (Фаза 6)

- **CLI `retouch order`:** управление заказами из командной строки
  - `retouch order list` — список активных заказов (ID, станок, статус, CRM-привязка, клиент)
  - `retouch order validate ORD-2026-001` — валидация order.json по schema.json
  - `retouch order create ORD-2026-042 --crm CMP-0042 -m impact` — создание заказа из шаблона с привязкой к CRM
- **CRM-связь:** поле `crm_company_id` в order.json (формат `CMP-NNNN`) — конвенционная связь заказов с компаниями в granite-crm
  - `schema.json`: добавлен `pattern: "^CMP-\\d{4}$"` для валидации ID
  - `orders/template/order.json`: поле `crm_company_id` включено в шаблон
- **config.yaml:** секция `crm:` с путём к granite-crm (`crm_path`) и переменной окружения (`GRANITE_CRM_PATH`)
- **GIMP-команда:** помечена как experimental / not recommended (предупреждение при запуске `retouch gimp`)
- **AGENTS.md:** обновлено дерево структуры (добавлен `retouch/` пакет, `BACKLOG.md`, `Makefile`), добавлена секция «Интеграция с granite-crm»
- **BACKLOG.md:** создан product backlog проекта (11 задач P0–P3)

## [2.3.1] - 2026-05-04

### 🔧 Дозакрытие Фазы 5

- **`retouch/__main__.py`:** добавлен — `python -m retouch` теперь работает (раньше: `No module named retouch.__main__`)
- **Корневые скрипты → тонкие обёртки:** `prepare_vignette.py` и `run_gimp.py` делегируют в `retouch.cli`, дублирование кода устранено
  - Если пакет не установлен — понятная ошибка с инструкцией `uv pip install -e .`
- **Makefile:** шорткаты для повседневных команд (`make process`, `make validate`, `make gimp`, `make test`, `make install-dev`)

## [2.3.0] - 2026-05-04

### 🏗️ Реструктуризация архитектуры (Фаза 5)

- **Пакет `retouch/`:** код вынесен из монолитных скриптов в модульную структуру
  - `retouch/config.py` — загрузка config.yaml
  - `retouch/cli.py` — единая точка входа (`python -m retouch process|validate|gimp`)
  - `retouch/processing/chromakey.py` — удаление синего фона + fringe removal
  - `retouch/processing/glow.py` — Inner Glow (contour light)
  - `retouch/processing/levels.py` — Levels + Unsharp Mask + контроль яркости
  - `retouch/processing/vignette.py` — арховая виньетка
  - `retouch/processing/pipeline.py` — полный пайплайн
  - `retouch/gimp/runner.py` — поиск и запуск GIMP
  - `retouch/validation/image.py` — валидация изображения и хромакея
  - `retouch/validation/order.py` — валидация order.json по schema.json
- **CLI:** `python -m retouch process -i ... -o ... -m laser` (устаревшее значение `"laser"`, используйте `"laser_standard"`)
- **pyproject.toml:** `retouch` CLI entry point, `packages = ["retouch"]`
- **Обратная совместимость:** `prepare_vignette.py` и `run_gimp.py` в корне по-прежнему работают

## [2.2.0] - 2026-05-04

### ⚡ Оптимизация обработки (Фаза 4)

- **numpy-ускорение:** `list(img.getdata())` заменён на `np.array()` — ~50x быстрее для 2048x2048
  - `remove_blue_background()` — numpy + scipy.ndimage.binary_dilation
  - `validate_blue_chromakey()` — numpy-подсчёт вместо Python-loop
  - `validate_result_black_ratio()` — numpy вместо list comprehension
  - Pillow-fallback сохранён (работает без numpy, но медленнее)
- **Fringe removal:** мягкое гашение синего канала в переходной зоне (артефакты хромакея на волосах/краях)
  - `fringe_radius` в config.yaml (default: 3, 0 = отключено)
  - numpy: binary_dilation + weighted blue damping
  - Pillow: pixel-level fallback
- **Контроль яркости лица:** `check_face_brightness()` — проверка средней яркости субъекта
  - laser: целевой диапазон 230-245, impact: 220-235
  - Автокоррекция brightness factor если вне диапазона (0.85-1.25)
  - Работает с numpy и Pillow (ImageStat fallback)
- **Зависимости:** добавлены `numpy>=1.24.0`, `scipy>=1.10.0` в pyproject.toml и requirements.txt

## [2.1.0] - 2026-05-04

### 🛡️ Валидация и обработка ошибок (Фаза 3)

- **prepare_vignette.py:**
  - `validate_image_input()` — проверка существования файла, формата, разрешения (>=512x512)
  - `validate_blue_chromakey()` — проверка наличия синего хромакея (минимум 15% синих пикселей)
  - `validate_result_black_ratio()` — проверка результата (минимум 25% чёрного фона)
  - Класс `ValidationError` с понятными сообщениями об ошибках
  - Флаг `--no-validate` для обхода валидации
  - Автосоздание директории для выходного файла
  - Исправлена генерация PNG-имени когда выходной файл не .tiff
- **config.yaml:** добавлены параметры `min_blue_ratio`, `min_resolution`, `result_min_black_ratio`
- **pyproject.toml:** добавлен `[build-system]`, явное указание `py-modules` и `packages = []` (исправлена ошибка setuptools flat-layout)
- **.gitignore:** убраны `*.lock` и `uv.lock` — lock-файлы должны коммититься

## [2.0.0] - 2026-05-04

### 🔄 Миграция

- Проект переименован: MEMORIAL → granite-retouch
- funeral-scraper удалён из документации (функции перенесены в granite-crm)
- `.agents/skills/` переименованы: memorial-* → retouch-*
- `memorial_process.scm` → `retouch_process.scm`
- `prepare_vignette.py`: функция `apply_memorial_processing` → `apply_retouch_processing`
- `run_gimp.bat` → `run_gimp.py` (Python CLI с автопоиском GIMP)
- Удалены `vibe.bat`, `projects/`, `sdk_page_reader_agent_guide.md`, `cities_russia_500k.md`

### 🐛 Исправления

- **prepare_vignette.py:** параметр `machine_type` теперь реально используется — impact и laser имеют разные параметры Inner Glow и яркости
- **retouch_process.scm:** виньетка масштабируется по размеру изображения (вместо захардкоженных 400/800 px)
- **retouch_process.scm:** добавлен параметр `machine-type` для дифференциации Inner Glow (shrink, feather, opacity)

### ✨ Новые возможности

- **prepare_vignette.py:** CLI через argparse (`--input`, `--output`, `--machine`, `--glow-size`, `--glow-opacity`)
- **run_gimp.py:** Python-скрипт с автопоиском GIMP по стандартным путям и env var `GIMP_PATH`
- **orders/schema.json:** добавлен `pattern` для `order_id`, `enum` для `clothing_style`/`headgear`/`face_quality`, поле `crm_company_id`
- **.gitignore:** защита от попадания бинарников из orders/active/

## [1.2.0] - 2026-03-14

### ✨ Новые возможности

- **funeral-agency-db:** Новая подсистема для сбора базы ритуальных агентств и производителей памятников по городам России.
  - Поиск организаций в 2GIS, Яндекс.Картах, справочниках (Yell.ru, JSprav.ru)
  - Обязательный поиск Telegram/WhatsApp по номерам телефонов
  - Приоритет контактов: Telegram > WhatsApp > Email > Телефон
  - Формат ссылок: t.me/username, wa.me/79xxxxxxxxx
  - Сбор данных по 26+ организациям в каждом городе

### 🔧 Улучшения

- **AGENTS.md:** Обновлена структура проекта, добавлена документация по funeral-scraper
- **README.md:** Добавлена секция funeral-agency-db
- **Агент funeral-scraper:** Обновлены инструкции с приоритетом Telegram

## [1.1.0] - 2026-03-11

### ✨ Новые возможности

- **AGENTS.md**: Создано руководство для ИИ-агентов с полной документацией по проекту.
  - Команды для валидации JSON
  - Стиль кода (Markdown, JSON, файлы)
  - Инструкции по работе с агентами
  - Соглашения об именовании

### 🔧 Улучшения

- **Структура документации**: Добавлена ссылка на AGENTS.md в README.md

## [1.0.0] - 2026-03-11

### ✨ Новые возможности

- **Агентская архитектура (Antigravity Skills):**
  - Навык `memorial-analyzer` — анализ фото и заполнение профиля заказа
  - Навык `memorial-prompter` — сборка промптов из атомарных блоков
  - Чек-лист `memorial-postprocessing` — подготовка к гравировке в Photoshop
- **Управление заказами:**
  - Структура папок: `orders/active/`, `orders/archive/`
  - JSON-схема `orders/schema.json` для стандартизации
  - Шаблон заказа и тестовый пример `TEST_ORDER`
- **База знаний:**
  - Спецификация [лазерных](knowledge/machines/laser.md) и [ударных](knowledge/machines/impact.md) станков
  - Принципы ретуши в `knowledge/principles.md`
- **Библиотека промптов:**
  - Блоки для базовых инструкций, станков, одежды, головных уборов
- **Навигация:** Переработан `workflow.md`

### 🔧 Улучшения

- **README.md**: Обновлен с учетом агентской структуры
- **Workflow**: Переход на итеративное взаимодействие с агентами

### 🗑 Удалено

- Устаревшая документация: `pipeline_laser.md`, `pipeline_impact.md`, `правки портрета.txt`

## [0.1.0] - 2026-03-10

- Начальная версия с базовой документацией по пайплайнам
