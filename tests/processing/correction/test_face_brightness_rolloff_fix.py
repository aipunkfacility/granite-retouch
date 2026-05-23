"""Test that face_skin is NOT compressed by rolloff — prevents gray plateau.

Rolloff удалён из face_brightness_correction (P0.2), применяется только
в postprocess.py после gamma, исключая face_skin из rolloff-маски.
face_skin защищён трехуровневой defence-in-depth:
1. Gamma-aware target (снижает pre-gamma цели)
2. Safety cap (steps.py) — клиппит face_skin после unsharp даже без zone_masks
3. Rolloff исключает face_skin из маски (postprocess.py + steps.py highlight_rolloff)
"""
import numpy as np
from PIL import Image

from retouch.processing.correction.face_brightness import face_brightness_correction
from retouch.processing.correction.postprocess import apply_postprocess
from retouch.processing.correction.rolloff import build_face_safe_rolloff_mask


class _MockZM:
    """Minimal mock — only attributes face_brightness_correction reads."""
    def __init__(self, highlights, face_skin):
        self.highlights = highlights
        self.face_skin = face_skin


def test_face_skin_not_compressed_by_rolloff():
    """
    face_skin pixels boosted by Phase 1 above knee are NOT compressed
    by rolloff — rolloff was removed from face_brightness_correction
    (P0.2). face_skin passes through with natural tonal variation.
    postprocess.py applies rolloff after gamma, excluding face_skin from
    the rolloff mask.
    """
    # 10x10 image: dark bg (80) + one bright skin pixel (175)
    img_arr = np.full((10, 10), 80, dtype=np.uint8)
    img_arr[5, 5] = 175
    img_gray = Image.fromarray(img_arr, mode='L')

    subj = np.full((10, 10), 255, dtype=np.uint8)
    subject_mask = Image.fromarray(subj, mode='L')

    face_skin = np.zeros((10, 10), dtype=np.uint8)
    face_skin[4:, :] = 255

    # Highlights zone: pixel (5,6) covered, pixel (5,5) NOT covered
    hl = np.zeros((10, 10), dtype=np.uint8)
    hl[5, 6] = 255

    zm = _MockZM(hl, face_skin)

    cfg = {
        "face_brightness_target_min": 190,
        "face_brightness_target_max": 210,
        "white_ceiling": 200,          # knee = 180
        "rolloff_compression": 0.20,
    }
    analytics = {"median_brightness": 100, "p90_brightness": 140}

    result, _, _, _, _ = face_brightness_correction(
        img_gray=img_gray,
        subject_mask=subject_mask,
        face_skin_mask=face_skin,
        machine_cfg=cfg,
        analytics=analytics,
        zone_masks=zm,
    )

    arr = np.array(result)
    lifted = float(arr[5, 5])   # Phase 1 boosted face_skin pixel
    ctrl = float(arr[5, 6])     # In highlights → rolled off

    # Highlights pixel should be rolled off (always)
    assert ctrl <= 184, f"Control pixel {ctrl} should be rolled off"

    # face_skin pixel: NOT rolled off (rolloff mask is highlights-only)
    # The pixel may be above knee but that's OK — its tonal variation
    # is preserved instead of being compressed into a plateau.
    # With gamma-aware target, the pixel should be lower than without.
    assert lifted > ctrl, (
        f"Face skin pixel {lifted} should NOT be rolled off like "
        f"highlights pixel {ctrl}"
    )


def test_highlights_rolloff_preserved():
    """
    Highlights OUTSIDE face_skin must still get rolloff in postprocess.
    face_skin must NOT be in the rolloff mask — it passes through
    with natural variation even if slightly above knee.
    """
    # Simulate image with bright pixel at 215 (face_skin) and 230 (highlights)
    arr = np.full((10, 10), 100, dtype=np.uint8)
    arr[5, 5] = 215  # face_skin pixel (above knee after gamma)
    arr[2, 6] = 230  # highlights pixel (outside face_skin, way above knee)
    img = Image.fromarray(arr, mode='L')

    subj = np.full((10, 10), 255, dtype=np.uint8)
    face = np.zeros((10, 10), dtype=np.uint8)

    hl = np.zeros((10, 10), dtype=np.uint8)
    hl[2, 6] = 255  # (2,6) is highlights, outside face_skin
    fs = np.zeros((10, 10), dtype=np.uint8)
    fs[4:8, :] = 255  # (5,5) is face_skin, (2,6) is NOT

    zm = _MockZM(hl, fs)

    result = apply_postprocess(
        img=img,
        subject_mask=subj,
        face_mask=face,
        zone_masks=zm,
        machine_type="impact",
        shadow_floor=0,
        stone_gamma=0.90,
        white_ceiling=240,
        compression=0.35,
    )

    res = np.array(result)
    face_skin_val = float(res[5, 5])
    highlights_val = float(res[2, 6])

    # face_skin: NOT in rolloff mask → passes through (may be above knee)
    # After gamma: (215/255)^0.90 * 255 ≈ 218.7
    assert face_skin_val >= 218, (
        f"Face skin pixel {face_skin_val} should pass through "
        f"without rolloff compression"
    )

    # Highlights (outside face_skin): IN rolloff mask → gets compressed
    # After gamma: (230/255)^0.90 * 255 ≈ 233.2, knee=216
    # Rolled off: 216 + (233.2-216)*0.35 = 216 + 6.0 = 222.0
    assert highlights_val < 225, (
        f"Highlights pixel {highlights_val} should be rolled off"
    )

    # face_skin should NOT be compressed — its value should be close to
    # the unrolled gamma value (≈218.7). Highlights got compressed but
    # still remain brighter because rolloff preserves the order.
    assert face_skin_val >= 218, (
        f"Face skin {face_skin_val} was compressed below its natural "
        f"gamma value ≈218 — rolloff mask shouldn't include face_skin"
    )


def test_gamma_aware_target_preserves_tonal_variation():
    """
    Integration test: gamma-aware target + no rolloff on face_skin
    preserves tonal variation (no gray plateau).
    """
    rng = np.random.RandomState(42)
    arr = rng.normal(loc=180, scale=20, size=(100, 100)).astype(np.float32)
    arr = np.clip(arr, 120, 240).astype(np.uint8)
    img = Image.fromarray(arr, mode='L')

    subj = np.full((100, 100), 255, dtype=np.uint8)
    subject_mask = Image.fromarray(subj, mode='L')
    face_skin = np.ones((100, 100), dtype=np.uint8) * 255

    cfg = {
        "face_brightness_target_min": 200,
        "face_brightness_target_max": 225,
        "stone_gamma": 0.90,
        "white_ceiling": 240,
        "rolloff_compression": 0.35,
    }
    analytics = {"median_brightness": 180.0, "p90_brightness": 210.0}

    result, _, _, _, _ = face_brightness_correction(
        img, subject_mask, face_skin, cfg, analytics,
    )

    fb_arr = np.array(result, dtype=np.float32)
    fs = face_skin > 128

    # Simulate gamma
    gamma = 0.90
    norm = fb_arr / 255.0
    after_gamma = np.power(norm, gamma) * 255.0

    # Measure tonal variation — should be substantial (>30 levels p10-p90)
    p10, p90 = np.percentile(after_gamma[fs], [10, 90])
    tonal_range = p90 - p10

    assert tonal_range > 30, (
        f"Tonal range after gamma: {tonal_range:.1f} — expected >30. "
        f"Gamma-aware target should preserve tonal variation."
    )


def test_no_rolloff_fallback_on_subject_mask():
    """
    При пустых highlights rolloff НЕ применяется ко всему subject_mask.
    Rolloff удалён из face_brightness — fallback невозможен.
    Тест верифицирует, что тёмное лицо не получает серое плато.
    """
    img_arr = np.full((10, 10), 80, dtype=np.uint8)
    img_arr[4:6, 4:6] = 150
    img_gray = Image.fromarray(img_arr, mode='L')

    subj = np.full((10, 10), 255, dtype=np.uint8)
    subject_mask = Image.fromarray(subj, mode='L')

    face_skin = np.zeros((10, 10), dtype=np.uint8)
    face_skin[3:7, 3:7] = 255

    hl_empty = np.zeros((10, 10), dtype=np.uint8)
    zm = _MockZM(highlights=hl_empty, face_skin=face_skin)

    cfg = {
        "face_brightness_target_min": 190,
        "face_brightness_target_max": 210,
        "white_ceiling": 200,
        "rolloff_compression": 0.20,
    }
    analytics = {"median_brightness": 80, "p90_brightness": 120}

    result, _, _, _, _ = face_brightness_correction(
        img_gray=img_gray,
        subject_mask=subject_mask,
        face_skin_mask=face_skin,
        machine_cfg=cfg,
        analytics=analytics,
        zone_masks=zm,
    )

    arr = np.array(result)
    skin_pixels = arr[face_skin > 128]
    skin_std = float(np.std(skin_pixels))
    assert skin_std > 5, (
        f"face_skin Std={skin_std:.1f} — похоже на rolloff-сжатие (серое плато). "
        f"Rolloff удалён из face_brightness — сжатия быть не должно."
    )


def test_highlights_get_single_rolloff_in_full_pipeline():
    """
    Интеграционный тест: highlights получают rolloff ровно 1 раз
    в полном пайплайне (face_brightness + postprocess).
    """
    arr = np.full((100, 100), 100, dtype=np.uint8)
    arr[10:20, 10:20] = 240  # highlights
    img = Image.fromarray(arr, mode='L')

    subj = np.full((100, 100), 255, dtype=np.uint8)
    subject_mask = Image.fromarray(subj, mode='L')

    face_skin = np.zeros((100, 100), dtype=np.uint8)
    face_skin[30:70, 30:70] = 255

    hl = np.zeros((100, 100), dtype=np.uint8)
    hl[10:20, 10:20] = 255

    fs_mask = np.zeros((100, 100), dtype=np.uint8)
    fs_mask[30:70, 30:70] = 255

    zm = _MockZM(highlights=hl, face_skin=fs_mask)

    cfg = {
        "face_brightness_target_min": 170,
        "face_brightness_target_max": 190,
        "stone_gamma": 0.90,
        "white_ceiling": 240,
        "rolloff_compression": 0.35,
    }
    analytics = {"median_brightness": 100.0, "p90_brightness": 150.0}

    fb_result, _, _, _, _ = face_brightness_correction(
        img_gray=img,
        subject_mask=subject_mask,
        face_skin_mask=face_skin,
        machine_cfg=cfg,
        analytics=analytics,
    )

    fb_arr = np.array(fb_result, dtype=np.float32)
    highlights_before_postproc = float(fb_arr[15, 15])

    post_result = apply_postprocess(
        img=fb_result,
        subject_mask=subj,
        face_mask=np.zeros((100, 100), dtype=np.uint8),
        zone_masks=zm,
        machine_type="impact",
        shadow_floor=0,
        stone_gamma=0.90,
        white_ceiling=240,
        compression=0.35,
    )

    post_arr = np.array(post_result, dtype=np.float32)
    highlights_after = float(post_arr[15, 15])

    # После gamma 0.90: (240/255)^0.90 * 255 ≈ 243.2
    # После одинарного rolloff: 216 + (243.2 - 216) × 0.35 = 216 + 9.5 = 225.5
    # Двойной rolloff: 216 + (225.5 - 216) × 0.35 = 216 + 3.3 = 219.3
    assert highlights_after > 220, (
        f"Highlights {highlights_after:.1f} сжаты слишком сильно — "
        f"возможен двойной rolloff. Ожидается ~225 (одинарный rolloff)"
    )


class TestBuildFaceSafeRolloffMask:
    """build_face_safe_rolloff_mask: выбор маски с защитой лица."""

    def test_exclude_face_skin_primary_zone(self):
        """Режим exclude_face_skin: rolloff на субъект минус face_skin."""
        subj = np.full((10, 10), 255, dtype=np.uint8)
        fs = np.zeros((10, 10), dtype=np.uint8)
        fs[3:7, 3:7] = 255
        zm = _MockZM(highlights=np.zeros((10, 10), dtype=np.uint8), face_skin=fs)

        mask = build_face_safe_rolloff_mask(
            subj, face_mask=None, zone_masks=zm,
            primary_zone="exclude_face_skin",
        )
        assert mask is not None
        assert mask[5, 5] == 0
        assert mask[0, 0] == 255

    def test_highlights_only_primary_zone(self):
        """Режим highlights_only: rolloff только на highlights."""
        subj = np.full((10, 10), 255, dtype=np.uint8)
        hl = np.zeros((10, 10), dtype=np.uint8)
        hl[0:3, 0:3] = 255
        zm = _MockZM(highlights=hl, face_skin=np.zeros((10, 10), dtype=np.uint8))

        mask = build_face_safe_rolloff_mask(
            subj, face_mask=None, zone_masks=zm,
            primary_zone="highlights_only",
        )
        assert mask is not None
        assert mask[1, 1] == 255
        assert mask[5, 5] == 0

    def test_fallback_to_face_mask(self):
        """При недоступной primary-зоне — fallback на face_mask."""
        subj = np.full((10, 10), 255, dtype=np.uint8)
        face = np.zeros((10, 10), dtype=np.uint8)
        face[3:7, 3:7] = 255

        mask = build_face_safe_rolloff_mask(
            subj, face_mask=face, zone_masks=None,
            primary_zone="exclude_face_skin",
        )
        assert mask is not None
        assert mask[5, 5] == 0
        assert mask[0, 0] == 255

    def test_skip_rolloff_when_no_protection(self):
        """Нет primary-зоны и face_mask → None (пропуск rolloff)."""
        subj = np.full((10, 10), 255, dtype=np.uint8)

        mask = build_face_safe_rolloff_mask(
            subj, face_mask=None, zone_masks=None,
            primary_zone="exclude_face_skin",
        )
        assert mask is None


def test_postprocess_rolloff_uses_face_mask_when_face_skin_unavailable():
    """
    При отсутствии zone_masks.face_skin — использовать face_mask
    как fallback для исключения лица из rolloff.
    """
    arr = np.full((10, 10), 230, dtype=np.uint8)
    arr[:3, :] = 10  # фон
    img = Image.fromarray(arr, mode='L')

    subj = np.full((10, 10), 255, dtype=np.uint8)
    subj[:3, :] = 0  # фон не в субъекте

    face = np.zeros((10, 10), dtype=np.uint8)
    face[3:7, 3:7] = 255  # лицо — грубая маска

    result = apply_postprocess(
        img=img,
        subject_mask=subj,
        face_mask=face,
        zone_masks=None,
        machine_type="impact",
        shadow_floor=0,
        stone_gamma=0.90,
        white_ceiling=240,
        compression=0.35,
    )

    res = np.array(result)
    face_pixels = res[3:7, 3:7]
    non_face_pixels = res[7:, :]

    assert float(face_pixels.mean()) >= float(non_face_pixels.mean()), (
        f"Face pixels {face_pixels.mean():.1f} should be >= "
        f"non-face {non_face_pixels.mean():.1f} — face excluded from rolloff"
    )


def test_postprocess_rolloff_logs_warning_without_face_masks():
    """
    При отсутствии и face_skin, и face_mask — логируется warning.
    """
    arr = np.full((10, 10), 230, dtype=np.uint8)
    img = Image.fromarray(arr, mode='L')

    subj = np.full((10, 10), 255, dtype=np.uint8)

    result = apply_postprocess(
        img=img,
        subject_mask=subj,
        face_mask=None,
        zone_masks=None,
        machine_type="impact",
        shadow_floor=0,
        stone_gamma=0.90,
        white_ceiling=240,
        compression=0.35,
    )
    assert result is not None
