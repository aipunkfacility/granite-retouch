# Processing Module Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `retouch/processing/` from flat 18 files into 5 domain subdirectories without changing any runtime behavior. All public API exports from `retouch.processing` remain identical.

**Architecture:** New layout:
```
retouch/processing/
├── __init__.py          ← re-exports from subdirs (unchanged public API)
├── core/                ← pipeline, plan, gates
├── analysis/            ← analysis, metrics, zones
├── correction/          ← levels, face_correction, glow, unsharp,
│                          shadow_noise, gamma, rolloff, mask_utils
├── detection/           ← face_region, chromakey
└── output/              ← export, vignette
```

**Tech Stack:** Python 3.14, no new dependencies. All changes are purely mechanical import path updates.

**Migration strategy:** Write a Python script that transforms all import paths across the codebase. One pass, no manual edits on ~40 files.

---

### Task 0: Build migration script

**Files:**
- Create: `scripts/migrate-processing-imports.py`
- Run: once, then delete

- [ ] **Step 1: Write the migration script**

The script reads every `.py` file in the repo (excluding `.venv/`, `__pycache__/`, `.git/`) and applies the import path mapping.

```python
"""Migrate retouch.processing import paths after restructuring.

Run from repo root:
    python scripts/migrate-processing-imports.py

This is a one-time migration. Delete this file afterwards.
"""
from pathlib import Path

# Mapping: old module leaf → new subdir
LEAF_TO_SUBDIR = {
    "pipeline": "core",
    "plan": "core",
    "gates": "core",
    "analysis": "analysis",
    "metrics": "analysis",
    "zones": "analysis",
    "levels": "correction",
    "face_correction": "correction",
    "glow": "correction",
    "unsharp": "correction",
    "shadow_noise": "correction",
    "gamma": "correction",
    "rolloff": "correction",
    "mask_utils": "correction",
    "face_region": "detection",
    "chromakey": "detection",
    "export": "output",
    "vignette": "output",
}

REPO_ROOT = Path(__file__).resolve().parent.parent

# Build (old_pattern, new_pattern) for each leaf
# This handles both absolute (retouch.processing.X) and relative (.X) imports
MAPPINGS: list[tuple[str, str]] = []
for leaf, subdir in LEAF_TO_SUBDIR.items():
    MAPPINGS.append((f"from retouch.processing.{leaf} import", f"from retouch.processing.{subdir}.{leaf} import"))
    MAPPINGS.append((f"import retouch.processing.{leaf} as", f"import retouch.processing.{subdir}.{leaf} as"))
    MAPPINGS.append((f"import retouch.processing.{leaf}", f"import retouch.processing.{subdir}.{leaf}"))
    MAPPINGS.append((f"from .{leaf} import", f"from .{subdir}.{leaf} import"))

def migrate_file(filepath: Path) -> bool:
    old_text = filepath.read_text(encoding="utf-8")
    new_text = old_text
    for old, new in MAPPINGS:
        new_text = new_text.replace(old, new)
    if new_text != old_text:
        filepath.write_text(new_text, encoding="utf-8")
        return True
    return False

def main():
    all_files = list(REPO_ROOT.rglob("*.py"))
    exclude_dirs = {".venv", "__pycache__", ".git"}
    changed: list[str] = []
    for f in sorted(all_files):
        if any(part in exclude_dirs for part in f.parts):
            continue
        if migrate_file(f):
            changed.append(str(f))
    print(f"Updated {len(changed)} files:")
    for p in changed:
        print(f"  {p}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Save the script**

```bash
python scripts/migrate-processing-imports.py
```
Expected: lists ~40 modified files

---

### Task 1: Create subdirectory structure

**Files:**
- Create: `retouch/processing/core/__init__.py`
- Create: `retouch/processing/analysis/__init__.py`
- Create: `retouch/processing/correction/__init__.py`
- Create: `retouch/processing/detection/__init__.py`
- Create: `retouch/processing/output/__init__.py`

- [ ] **Step 1: Create 5 directories + empty __init__.py files**

```bash
$dirs = @("core", "analysis", "correction", "detection", "output")
foreach ($d in $dirs) {
    $path = "retouch/processing/$d"
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    Set-Content -Path "$path/__init__.py" -Value ""
}
```

---

### Task 2: Move files to subdirectories

**Files:** Move 17 `.py` files (excluding `__init__.py`) to their new subdirectories per the LEAF_TO_SUBDIR mapping.

- [ ] **Step 1: Move files**

```bash
Move-Item retouch/processing/pipeline.py retouch/processing/core/pipeline.py
Move-Item retouch/processing/plan.py retouch/processing/core/plan.py
Move-Item retouch/processing/gates.py retouch/processing/core/gates.py
Move-Item retouch/processing/analysis.py retouch/processing/analysis/analysis.py
Move-Item retouch/processing/metrics.py retouch/processing/analysis/metrics.py
Move-Item retouch/processing/zones.py retouch/processing/analysis/zones.py
Move-Item retouch/processing/levels.py retouch/processing/correction/levels.py
Move-Item retouch/processing/face_correction.py retouch/processing/correction/face_correction.py
Move-Item retouch/processing/glow.py retouch/processing/correction/glow.py
Move-Item retouch/processing/unsharp.py retouch/processing/correction/unsharp.py
Move-Item retouch/processing/shadow_noise.py retouch/processing/correction/shadow_noise.py
Move-Item retouch/processing/gamma.py retouch/processing/correction/gamma.py
Move-Item retouch/processing/rolloff.py retouch/processing/correction/rolloff.py
Move-Item retouch/processing/mask_utils.py retouch/processing/correction/mask_utils.py
Move-Item retouch/processing/face_region.py retouch/processing/detection/face_region.py
Move-Item retouch/processing/chromakey.py retouch/processing/detection/chromakey.py
Move-Item retouch/processing/export.py retouch/processing/output/export.py
Move-Item retouch/processing/vignette.py retouch/processing/output/vignette.py
```

---

### Task 3: Run migration script to update all imports

- [ ] **Step 1: Run the script**

```bash
python scripts/migrate-processing-imports.py
```

Verify: all `.py` files in the repo have been scanned and import paths updated.

- [ ] **Step 2: Run tests to check for import errors**

```bash
& ".venv/Scripts/python.exe" -m pytest tests/ --no-header -q -x --tb=short 2>&1
```

Expected: all tests pass (660 pass, 19 pre-existing fail). If import errors appear, the migration script missed some patterns — fix and re-run.

---

### Task 4: Update `retouch/processing/__init__.py` (main package)

**File:** `retouch/processing/__init__.py`

The migration script already updated relative imports from `.X` to `.subdir.X`. But `__init__.py` may have absolute imports too. Verify manually.

- [ ] **Step 1: Verify __init__.py is correct**

```bash
Get-Content retouch/processing/__init__.py
```

All imports should now point to `.core.pipeline`, `.output.export`, `.correction.levels`, etc.

- [ ] **Step 2: Run imports sanity check**

```bash
& ".venv/Scripts/python.exe" -c "from retouch.processing import process, export_result, apply_levels, ImageAnalytics, PipelinePlan; print('OK')"
```

Expected: `OK`

---

### Task 5: Verify no stale references

- [ ] **Step 1: Check for remaining references to old flat paths**

```bash
Select-String -Path (Get-ChildItem -Recurse -Filter "*.py" | Where-Object { $_.DirectoryName -notmatch '\.venv|__pycache__|\.git' }) -Pattern "from retouch\.processing\.(pipeline|plan|gates|analysis|metrics|zones|levels|face_correction|glow|unsharp|shadow_noise|gamma|rolloff|mask_utils|face_region|chromakey|export|vignette)\b"
```

Expected: no matches (all references now include the subdirectory). If any remain, the migration script missed some — handle manually.

- [ ] **Step 2: Full test suite**

```bash
& ".venv/Scripts/python.exe" -m pytest tests/ --no-header -q 2>&1 | Select-Object -Last 1
```

Expected: `19 failed, 660 passed` (same as before, no regressions)

---

### Task 6: Delete migration script

- [ ] **Step 1: Clean up**

```bash
Remove-Item scripts/migrate-processing-imports.py
```

---

### Task 7: Commit

- [ ] **Step 1: Commit all changes**

```bash
git add retouch/processing/
git add scripts/migrate-processing-imports.py  # included for history
git commit -m "refactor: restructure retouch/processing/ into domain subdirectories

- core/: pipeline, plan, gates
- analysis/: analysis, metrics, zones
- correction/: levels, face_correction, glow, unsharp, shadow_noise,
                gamma, rolloff, mask_utils
- detection/: face_region, chromakey
- output/: export, vignette
- All import paths updated across ~40 files
- __init__.py re-exports unchanged — public API preserved"
```

---

## Self-Review Checklist

- [x] Each task has exact file paths
- [x] Each task has complete commands
- [x] No placeholders or TODOs
- [x] Migration script handles all known import patterns (absolute + relative)
- [x] Verification step after migration
- [x] Rollback path: `git checkout HEAD -- retouch/processing/` if anything goes wrong
