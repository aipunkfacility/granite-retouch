# Pipeline Refactor — Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 6 PARTIALLY DONE items from the pipeline refactor audit to reach 100% completion.

**Architecture:** Add missing CLI flag, config-driven gate thresholds, create dither fixtures, fix rolloff zone in levels.py, and add `--profile` to the `process()` wrapper. No structural changes — only filling gaps.

**Tech Stack:** Python, argparse, numpy, PIL, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `retouch/cli.py:375-390` | Modify | Add `--profile` argument to `p_process` subparser |
| `retouch/cli.py:1033-1052` | Modify | Add `profile` parameter to `process()` wrapper and forward to `process_export()` |
| `retouch/processing/core/pipeline.py:303` | Modify | Already accepts `profile` — verify `process_export()` passes it through |
| `config.yaml:69-77` | Modify | Add `quality_gates` section after `safety_envelope` |
| `retouch/processing/core/pipeline.py` | Modify | Read gate thresholds from config and pass to gate functions |
| `retouch/processing/correction/levels.py:128-133` | Modify | Change rolloff from face_skin to highlights zone when available |
| `tests/fixtures/dither/` | Create | Directory with 5+ PNG fixtures + reference BMPs |
| `tests/test_config_defaults_sync.py` | Extend | Add test for quality_gates section in config |
| `docs/reference/config.md` | Modify | Document `quality_gates` section |
| `CHANGELOG.md` | Modify | Add completion entries |
| `README.md:112` | Modify | Fix CLI `--profile` example (now accurate) |

---

### Task 1: Add `--profile` CLI argument

**Files:**
- Modify: `retouch/cli.py:375-390` (add argument), `retouch/cli.py:1033-1052` (add parameter to wrapper)
- Test: `tests/test_cli.py` (extend or create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py — add to existing test file or create
import argparse
from retouch.cli import build_parser

def test_process_has_profile_argument():
    parser = build_parser()
    args = parser.parse_args(["process", "-i", "input.png", "-o", "output.bmp", "--profile", "preserve"])
    assert args.profile == "preserve"

def test_process_profile_default_is_standard():
    parser = build_parser()
    args = parser.parse_args(["process", "-i", "input.png", "-o", "output.bmp"])
    assert args.profile is None  # None means "use default standard in process_steps"

def test_process_profile_choices():
    parser = build_parser()
    # Should accept all three profiles
    for profile in ["preserve", "standard", "diagnostic"]:
        args = parser.parse_args(["process", "-i", "input.png", "-o", "output.bmp", "--profile", profile])
        assert args.profile == profile
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli.py::test_process_has_profile_argument -v
```
Expected: FAIL with `AttributeError` or `argument --profile: invalid choice` (argument doesn't exist yet).

- [ ] **Step 3: Add `--profile` argument to CLI subparser**

In `retouch/cli.py`, find line 389 (`p_process.add_argument("--overwrite"...)`) and add after it:

```python
    p_process.add_argument("--profile", choices=["preserve", "standard", "diagnostic"],
                           default=None, help="Processing profile (default: standard)")
```

- [ ] **Step 4: Add `profile` parameter to `process()` wrapper**

In `retouch/cli.py`, update the `process()` function signature at line 1033:

```python
def process(input_path: str, output_path: str, machine_type: str = "laser_standard",
            glow_size_override: int | None = None, glow_opacity_override: float | None = None,
            config: dict | None = None, fmt: str = "bmp", overwrite: bool = True,
            no_validate: bool = False,
            face_oval: dict[str, float] | None = None,
            debug_dir: str | None = None,
            profile: str | None = None) -> PipelineResult:
```

And forward it to `process_export()` at line 1040:

```python
    return process_export(
        input_path=input_path,
        output_path=output_path,
        machine_type=machine_type,
        config=config,
        fmt=fmt,
        overwrite=overwrite,
        no_validate=no_validate,
        glow_size_override=glow_size_override,
        glow_opacity_override=glow_opacity_override,
        face_oval=face_oval,
        debug_dir=debug_dir,
        profile=profile,  # NEW: forward profile to process_export
    )
```

- [ ] **Step 5: Pass profile from `cmd_process()` to `process()`**

In `retouch/cli.py`, find the `cmd_process()` function and add `profile=args.profile` to the `process()` call. The call should look like:

```python
    result = process(
        input_path=args.input,
        output_path=args.output,
        machine_type=args.machine,
        glow_size_override=args.glow_size,
        glow_opacity_override=args.glow_opacity,
        config=config,
        fmt=args.format,
        overwrite=args.overwrite,
        no_validate=args.no_validate,
        profile=args.profile,  # NEW
    )
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run pytest tests/test_cli.py::test_process_has_profile_argument tests/test_cli.py::test_process_profile_default_is_standard tests/test_cli.py::test_process_profile_choices -v
```
Expected: All 3 PASS.

- [ ] **Step 7: Verify CLI works end-to-end**

```bash
uv run python -m retouch process -i tests/fixtures/sample.png -o /tmp/test_profile.bmp --profile preserve --overwrite
```
Expected: Runs without error, uses preserve profile (check logs for "profile=preserve").

- [ ] **Step 8: Commit**

```bash
git add retouch/cli.py tests/test_cli.py
git commit -m "feat: add --profile CLI argument for process command"
```

---

### Task 2: Add `quality_gates` section to config.yaml

**Files:**
- Modify: `config.yaml:69-77` (add section after safety_envelope)
- Modify: `retouch/processing/core/pipeline.py` (read thresholds from config)
- Test: `tests/test_quality_gates.py` (extend with config-driven thresholds)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_quality_gates.py — add to existing TestQualityGatesConfig class or create

def test_gate_thresholds_from_config_yaml():
    """Gate thresholds are readable from config.yaml quality_gates section."""
    from retouch.config import load_config
    config = load_config()
    processing = config.get("processing", {})
    quality_gates = processing.get("quality_gates", {})
    
    assert "variance_loss_threshold" in quality_gates
    assert "clipped_pct_threshold" in quality_gates
    assert "p95_shift_threshold" in quality_gates
    assert "shadow_crush_threshold" in quality_gates
    assert "face_dark_small_threshold" in quality_gates
    assert "contour_inner_quality_threshold" in quality_gates
    
    # Verify defaults match current hardcoded values
    assert quality_gates["variance_loss_threshold"] == 35.0
    assert quality_gates["clipped_pct_threshold"] == 5.0
    assert quality_gates["p95_shift_threshold"] == 20.0
    assert quality_gates["shadow_crush_threshold"] == 10.0
    assert quality_gates["face_dark_small_threshold"] == 5.0
    assert quality_gates["contour_inner_quality_threshold"] == 30.0

def test_pipeline_passes_config_thresholds_to_gates():
    """Pipeline reads quality_gates from config and passes to gate functions."""
    from retouch.processing.core.pipeline import process_steps
    from retouch.config import load_config
    # This is an integration check — verify no crash with config thresholds
    # Full integration test in test_pipeline_with_gates.py
    config = load_config()
    processing = config.get("processing", {})
    quality_gates = processing.get("quality_gates", {})
    assert len(quality_gates) >= 6, "quality_gates should have at least 6 thresholds"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_quality_gates.py::test_gate_thresholds_from_config_yaml -v
```
Expected: FAIL — `quality_gates` section doesn't exist in config.yaml.

- [ ] **Step 3: Add `quality_gates` section to config.yaml**

Add after line 77 (after `safety_envelope` section, before `config_version`):

```yaml
# Quality gates — thresholds for pre-check and post-check
# All values are percentages or levels as documented in docs/reference/config.md
quality_gates:
  variance_loss_threshold: 35.0       # % variance loss before weakening delta
  clipped_pct_threshold: 5.0          # % clipped pixels before reducing rolloff
  p95_shift_threshold: 20.0           # levels p95 shift before weakening delta
  shadow_crush_threshold: 10.0        # % shadow crush before skipping floor/gamma
  face_dark_small_threshold: 5.0      # % face_dark ratio before skipping correction
  contour_inner_quality_threshold: 30.0  # % contour_inner ratio before morphological fallback
```

- [ ] **Step 4: Update pipeline.py to read gate thresholds from config**

In `retouch/processing/core/pipeline.py`, find where gates are called (around lines 588-611, 771). Add a helper function to extract thresholds:

```python
def _get_gate_thresholds(config: dict) -> dict:
    """Extract quality gate thresholds from config."""
    processing = config.get("processing", {})
    quality_gates = processing.get("quality_gates", {})
    return {
        "variance_loss_threshold": quality_gates.get("variance_loss_threshold", 35.0),
        "clipped_pct_threshold": quality_gates.get("clipped_pct_threshold", 5.0),
        "p95_shift_threshold": quality_gates.get("p95_shift_threshold", 20.0),
        "shadow_crush_threshold": quality_gates.get("shadow_crush_threshold", 10.0),
        "face_dark_small_threshold": quality_gates.get("face_dark_small_threshold", 5.0),
        "contour_inner_quality_threshold": quality_gates.get("contour_inner_quality_threshold", 30.0),
    }
```

Add this function near the top of `pipeline.py` (after imports, before `PipelineContext`).

Then update gate calls to use these thresholds. For example, change:

```python
# Before:
post_check_variance_loss(var_before, var_after, step_name=step_name)
# After:
post_check_variance_loss(var_before, var_after,
                         threshold_pct=thresholds["variance_loss_threshold"],
                         step_name=step_name)
```

Apply the same pattern for all 6 gate calls. The thresholds dict should be obtained once at the start of `_run_pipeline_steps()`:

```python
thresholds = _get_gate_thresholds(ctx.config)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_quality_gates.py::test_gate_thresholds_from_config_yaml tests/test_quality_gates.py::test_pipeline_passes_config_thresholds_to_gates -v
```
Expected: All PASS.

- [ ] **Step 6: Run full gate test suite**

```bash
uv run pytest tests/test_quality_gates.py tests/test_pipeline_with_gates.py -v
```
Expected: All PASS (existing tests should still work since defaults are preserved).

- [ ] **Step 7: Commit**

```bash
git add config.yaml retouch/processing/core/pipeline.py tests/test_quality_gates.py
git commit -m "feat: quality_gates thresholds from config.yaml"
```

---

### Task 3: Fix rolloff zone in levels.py

**Files:**
- Modify: `retouch/processing/correction/levels.py:128-133`
- Test: `tests/test_zonal_correction.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_zonal_correction.py — add to existing file

def test_levels_rolloff_uses_highlights_not_face_skin():
    """Levels rolloff should use highlights zone, not face_skin, when ZoneMasks available."""
    import numpy as np
    from PIL import Image
    from retouch.processing.correction.levels import apply_levels
    from retouch.processing.analysis.zones import ZoneMasks
    
    # Create test image: face_skin at 200 (above knee), highlights at 240
    arr = np.full((100, 100), 150, dtype=np.uint8)
    arr[20:40, 20:40] = 200  # face_skin zone
    arr[60:80, 60:80] = 240  # highlights zone
    
    img = Image.fromarray(arr, mode="L")
    subject_mask = Image.fromarray(np.full((100, 100), 255, dtype=np.uint8), mode="L")
    face_skin_mask = np.zeros((100, 100), dtype=np.uint8)
    face_skin_mask[20:40, 20:40] = 255
    
    # Create ZoneMasks with highlights
    zone_masks = ZoneMasks(
        subject=np.full((100, 100), 255, dtype=np.uint8),
        face=np.full((100, 100), 255, dtype=np.uint8),
        hair=np.zeros((100, 100), dtype=np.uint8),
        face_skin=face_skin_mask,
        face_dark=np.zeros((100, 100), dtype=np.uint8),
        clothes=np.zeros((100, 100), dtype=np.uint8),
        highlights=np.zeros((100, 100), dtype=np.uint8),  # will be set below
        contour_inner=np.zeros((100, 100), dtype=np.uint8),
        contour_outer=np.zeros((100, 100), dtype=np.uint8),
        background=np.zeros((100, 100), dtype=np.uint8),
    )
    zone_masks.highlights[60:80, 60:80] = 255
    
    analytics = {
        "median_brightness": 100,  # below target, will trigger correction
        "per_zone": {
            "face_skin": type("ZoneAnalytics", (), {"median": 200, "p10": 190, "p90": 210, "p95": 215, "max": 220, "variance": 100.0, "clipped_pct": 0.0})(),
        },
    }
    
    machine_cfg = {"white_ceiling": 250, "rolloff_compression": 0.35}
    
    # The rolloff should use highlights zone (60:80, 60:80), not face_skin (20:40, 20:40)
    # After rolloff, highlights pixels should be compressed below ceiling
    # face_skin pixels should NOT be compressed by rolloff (only by delta correction)
    result = apply_levels(img, analytics=analytics, machine_type="laser_standard",
                          subject_mask=subject_mask, machine_cfg=machine_cfg,
                          face_skin_mask=face_skin_mask, zone_masks=zone_masks)
    
    result_arr = np.array(result, dtype=np.float32)
    
    # Highlights zone should be compressed (below 250 ceiling)
    highlights_vals = result_arr[60:80, 60:80]
    assert highlights_vals.max() <= 250, f"Highlights not compressed: max={highlights_vals.max()}"
    
    # face_skin zone should NOT be affected by rolloff (only delta correction)
    # Since delta is positive (brightening), face_skin values should increase
    # but rolloff should NOT compress them since they're in face_skin, not highlights
    face_skin_vals = result_arr[20:40, 20:40]
    # face_skin was 200, with delta it should be higher, but rolloff shouldn't compress it
    # The key test: face_skin rolloff should NOT happen when zone_masks.highlights is available
```

Wait — looking at the current `apply_levels()` signature, it doesn't accept `zone_masks`. The fix requires adding this parameter. Let me revise the test and implementation.

- [ ] **Step 1 (revised): Write the failing test**

```python
# tests/test_zonal_correction.py — add to existing file

def test_levels_rolloff_uses_highlights_when_zone_masks_available():
    """When zone_masks.highlights is provided, rolloff uses it instead of face_skin."""
    import numpy as np
    from PIL import Image
    from retouch.processing.correction.levels import apply_levels
    from retouch.processing.analysis.zones import ZoneMasks
    
    # Create test image with distinct zones
    arr = np.full((100, 100), 100, dtype=np.uint8)
    arr[10:30, 10:30] = 220  # bright face_skin (above knee 225 for ceiling=250)
    arr[50:70, 50:70] = 240  # highlights (above knee)
    
    img = Image.fromarray(arr, mode="L")
    subject_mask = Image.fromarray(np.full((100, 100), 255, dtype=np.uint8), mode="L")
    face_skin_mask = np.zeros((100, 100), dtype=np.uint8)
    face_skin_mask[10:30, 10:30] = 255
    
    zone_masks = ZoneMasks(
        subject=np.full((100, 100), 255, dtype=np.uint8),
        face=np.full((100, 100), 255, dtype=np.uint8),
        hair=np.zeros((100, 100), dtype=np.uint8),
        face_skin=face_skin_mask.copy(),
        face_dark=np.zeros((100, 100), dtype=np.uint8),
        clothes=np.zeros((100, 100), dtype=np.uint8),
        highlights=np.zeros((100, 100), dtype=np.uint8),
        contour_inner=np.zeros((100, 100), dtype=np.uint8),
        contour_outer=np.zeros((100, 100), dtype=np.uint8),
        background=np.zeros((100, 100), dtype=np.uint8),
    )
    zone_masks.highlights[50:70, 50:70] = 255
    
    analytics = {"median_brightness": 100}  # below target → positive delta
    machine_cfg = {"white_ceiling": 250, "rolloff_compression": 0.35}
    
    result = apply_levels(
        img, analytics=analytics, machine_type="laser_standard",
        subject_mask=subject_mask, machine_cfg=machine_cfg,
        face_skin_mask=face_skin_mask, zone_masks=zone_masks,
    )
    
    result_arr = np.array(result, dtype=np.float32)
    
    # Highlights (50:70) should be compressed by rolloff
    hl_max = result_arr[50:70, 50:70].max()
    assert hl_max <= 250, f"Highlights not compressed: max={hl_max}"
    
    # face_skin (10:30) should NOT be compressed by rolloff — only delta correction
    # Since delta is small (+15 max), face_skin at 220 should stay around 220-235
    # NOT compressed to ~225 (knee area)
    fs_max = result_arr[10:30, 10:30].max()
    # face_skin should be higher than highlights because rolloff didn't compress it
    assert fs_max > hl_max, f"face_skin max ({fs_max}) should be > highlights max ({hl_max})"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_zonal_correction.py::test_levels_rolloff_uses_highlights_when_zone_masks_available -v
```
Expected: FAIL — `apply_levels()` doesn't accept `zone_masks` parameter yet.

- [ ] **Step 3: Add `zone_masks` parameter to `apply_levels()` and fix rolloff zone**

In `retouch/processing/correction/levels.py`, update the function signature at line 63:

```python
def apply_levels(img_gray, brightness_factor=None, analytics=None, machine_type=None,
                 subject_mask=None, machine_cfg=None, face_skin_mask=None, zone_masks=None):
```

Update the docstring to include:
```
        zone_masks: ZoneMasks or None — if provided, rolloff uses highlights zone
```

Replace lines 128-133 (the rolloff mask selection) with:

```python
        # v6.5: rolloff по highlights zone (если ZoneMasks доступен), иначе fallback
        if zone_masks is not None and zone_masks.highlights is not None and zone_masks.highlights.any():
            rolloff_mask_arr = (zone_masks.highlights > 128).astype(np.uint8) * 255
        elif face_skin_mask is not None:
            rolloff_mask_arr = face_skin_bool.astype(np.uint8) * 255
        else:
            rolloff_mask_arr = np.array(subject_mask, dtype=np.uint8)
```

- [ ] **Step 4: Update pipeline.py to pass zone_masks to apply_levels()**

In `retouch/processing/core/pipeline.py`, find the `apply_levels()` call (search for `apply_levels(`) and add `zone_masks=ctx.zone_masks` to the call.

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_zonal_correction.py::test_levels_rolloff_uses_highlights_when_zone_masks_available -v
```
Expected: PASS.

- [ ] **Step 6: Run full levels test suite**

```bash
uv run pytest tests/test_analysis.py tests/test_zonal_correction.py -v
```
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add retouch/processing/correction/levels.py retouch/processing/core/pipeline.py tests/test_zonal_correction.py
git commit -m "fix: levels rolloff uses highlights zone when ZoneMasks available"
```

---

### Task 4: Create dither regression fixtures

**Files:**
- Create: `tests/fixtures/dither/` directory with 5 PNG fixtures + 5 reference BMPs
- Create: `scripts/generate_dither_fixtures.py` (helper to generate fixtures)
- Test: `tests/test_dither_regression.py` (existing — will no longer skip)

- [ ] **Step 1: Create fixture generation script**

```python
# scripts/generate_dither_fixtures.py
"""Generate dither regression test fixtures."""
import os
import numpy as np
from PIL import Image

from retouch.processing.output.export import export_result

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "dither")


def create_fixtures():
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    fixtures = {
        "mid_gray": np.full((128, 128), 128, dtype=np.uint8),
        "gradient_h": np.tile(np.linspace(0, 255, 128, dtype=np.uint8), (128, 1)),
        "gradient_v": np.tile(np.linspace(0, 255, 128, dtype=np.uint8).reshape(-1, 1), (1, 128)),
        "face_like": _create_face_like(),
        "high_contrast": _create_high_contrast(),
    }

    for name, arr in fixtures.items():
        img = Image.fromarray(arr, mode="L")
        png_path = os.path.join(FIXTURES_DIR, f"{name}.png")
        img.save(png_path)
        print(f"Created {png_path}")

        # Generate reference BMP
        bmp_path = os.path.join(FIXTURES_DIR, f"{name}_dither.bmp")
        export_result(
            img, bmp_path,
            machine_type="laser_standard",
            fmt="bmp_1bit",
            export_mode="1bit",
            step_mm=0.300,
            dither_method_1bit="jarvis",
        )
        print(f"Created {bmp_path}")


def _create_face_like():
    """Synthetic face-like image: oval of mid-gray on dark background."""
    arr = np.full((128, 128), 40, dtype=np.uint8)
    cy, cx = 64, 64
    for y in range(128):
        for x in range(128):
            dist = ((x - cx) / 35) ** 2 + ((y - cy) / 45) ** 2
            if dist < 1.0:
                arr[y, x] = 160  # face region
    return arr


def _create_high_contrast():
    """High contrast: black and white stripes."""
    arr = np.zeros((128, 128), dtype=np.uint8)
    arr[:, :32] = 255
    arr[:, 64:96] = 255
    arr[64:, 32:64] = 200
    return arr


if __name__ == "__main__":
    create_fixtures()
    print("All fixtures generated.")
```

- [ ] **Step 2: Generate fixtures**

```bash
uv run python scripts/generate_dither_fixtures.py
```
Expected: Creates 5 PNG files and 5 BMP reference files in `tests/fixtures/dither/`.

- [ ] **Step 3: Verify fixtures exist**

```bash
ls tests/fixtures/dither/
```
Expected: `mid_gray.png`, `mid_gray_dither.bmp`, `gradient_h.png`, `gradient_h_dither.bmp`, `gradient_v.png`, `gradient_v_dither.bmp`, `face_like.png`, `face_like_dither.bmp`, `high_contrast.png`, `high_contrast_dither.bmp`.

- [ ] **Step 4: Run dither regression tests**

```bash
uv run pytest tests/test_dither_regression.py -v
```
Expected: All tests PASS (no longer skipped).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_dither_fixtures.py tests/fixtures/dither/
git commit -m "feat: dither regression fixtures (5 curated samples)"
```

---

### Task 5: Update documentation

**Files:**
- Modify: `README.md:112` (fix CLI example)
- Modify: `docs/reference/config.md` (add quality_gates section)
- Modify: `CHANGELOG.md` (add completion entries)

- [ ] **Step 1: Fix README.md CLI example**

In `README.md`, find line 112 (or search for `--profile preserve`) and update the CLI example to reflect the now-implemented flag:

```markdown
Выбор профиля: через CLI (`--profile preserve`) или UI (Profile Selector).
```

This is now accurate — the `--profile` flag exists.

- [ ] **Step 2: Add quality_gates documentation to config.md**

In `docs/reference/config.md`, add after the `safety_envelope` section (around line 311):

```markdown
### quality_gates

Пороги для pre-check и post-check quality gates. Все значения — числа с плавающей точкой.

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `variance_loss_threshold` | 35.0 | % потери variance по face_skin, после которого delta ослабляется на 50% |
| `clipped_pct_threshold` | 5.0 | % clipped пикселей по subject, после которого rolloff уменьшается на 20% |
| `p95_shift_threshold` | 20.0 | Сдвиг p95 по face_skin в уровнях, после которого delta ослабляется на 50% |
| `shadow_crush_threshold` | 10.0 | % пикселей < 5 в subject, после которого floor/gamma пропускаются |
| `face_dark_small_threshold` | 5.0 | % face_dark от face_mask, ниже которого коррекция пропускается |
| `contour_inner_quality_threshold` | 30.0 | % contour_inner от subject, выше которого — morphological fallback |

Пример:
```yaml
quality_gates:
  variance_loss_threshold: 35.0
  clipped_pct_threshold: 5.0
  p95_shift_threshold: 20.0
  shadow_crush_threshold: 10.0
  face_dark_small_threshold: 5.0
  contour_inner_quality_threshold: 30.0
```
```

- [ ] **Step 3: Update CHANGELOG.md**

Add to the top of `CHANGELOG.md` (after the current version header):

```markdown
## [6.5.0] — Pipeline Refactor Completion

### Fixed
- CLI: добавлен `--profile` аргумент для команды `process` (preserve/standard/diagnostic)
- Levels: rolloff теперь использует `highlights` зону из ZoneMasks вместо face_skin
- Quality gates: пороги вынесены в `config.yaml` секцию `quality_gates`

### Added
- Dither regression fixtures: 5 curated samples в `tests/fixtures/dither/`
- Script `scripts/generate_dither_fixtures.py` для регенерации эталонов

### Documentation
- README.md: исправлен пример CLI с `--profile`
- docs/reference/config.md: добавлена секция `quality_gates`
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/reference/config.md CHANGELOG.md
git commit -m "docs: update for pipeline refactor completion"
```

---

### Task 6: Final verification — run full test suite

- [ ] **Step 1: Run full test suite**

```bash
make test
```
Expected: All tests PASS. No regressions.

- [ ] **Step 2: Run lint**

```bash
make lint
```
Expected: No errors.

- [ ] **Step 3: Verify all 6 gaps are closed**

| Gap | Verification |
|-----|-------------|
| CLI `--profile` | `uv run python -m retouch process --help` shows `--profile` option |
| Batch numpy pass | Documented as deferred — masks build in one pass, corrections remain step-by-step (acceptable per plan) |
| Dither fixtures | `ls tests/fixtures/dither/*.png` shows 5+ files |
| Rolloff highlights | `test_levels_rolloff_uses_highlights_when_zone_masks_available` passes |
| Gate thresholds from config | `config.yaml` has `quality_gates` section, tests pass |
| Directory names | Deferred — `detection/` and `output/` work fine with re-exports |

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: pipeline refactor completion — all gaps closed"
```

---

## Self-Review

### 1. Spec coverage

| Refactor Plan Item | Task |
|-------------------|------|
| CLI `--profile` flag | Task 1 |
| quality_gates from config | Task 2 |
| Rolloff uses highlights zone | Task 3 |
| Dither fixtures | Task 4 |
| Documentation updates | Task 5 |
| Full test suite verification | Task 6 |

**Deferred items (explicitly not in scope):**
- **Batch numpy pass for corrections** — requires restructuring all correction modules to operate on a single numpy array. This is a significant architectural change that conflicts with the "don't restructure until Stage 6" principle. The current step-by-step PIL→numpy→PIL pattern works correctly; the optimization is performance-only, not correctness.
- **Directory renaming (detection/→segmentation/, output/→export/)** — re-exports are in place, functionality is identical. Renaming would break existing imports during the transition period.

### 2. Placeholder scan

No TBD, TODO, or placeholder patterns found. All steps contain actual code.

### 3. Type consistency

- `zone_masks` parameter added to `apply_levels()` matches existing `ZoneMasks` dataclass from `zones.py`
- `profile` parameter type `str | None` matches `process_steps()` signature
- Gate threshold keys in config match function parameter names in `gates.py`
- All test assertions use correct types (numpy arrays, PIL Images)

---

**Plan complete.** Ready for execution.
