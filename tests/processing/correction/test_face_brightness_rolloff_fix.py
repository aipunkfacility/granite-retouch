"""Test that face_skin is NOT compressed by rolloff — prevents gray plateau.

The rolloff mask must cover highlights ONLY, not face_skin. Applying rolloff
to face_skin compresses its tonal variation into a narrow band (gray plateau),
which is the root cause of the "face oval burnout" bug.

The gamma-aware target in face_brightness_correction keeps face_skin below
knee after gamma, so rolloff is not needed on face_skin.
"""
import numpy as np
from PIL import Image

from retouch.processing.correction.face_brightness import face_brightness_correction
from retouch.processing.correction.postprocess import apply_postprocess


class _MockZM:
    """Minimal mock — only attributes face_brightness_correction reads."""
    def __init__(self, highlights, face_skin):
        self.highlights = highlights
        self.face_skin = face_skin


def test_face_skin_not_compressed_by_rolloff():
    """
    face_skin pixels boosted by Phase 1 above knee should NOT be compressed
    by rolloff. Instead, the gamma-aware target keeps face_skin brightness
    lower so that after gamma it stays near (but not far above) knee,
    preserving tonal variation.

    If face_skin were in the rolloff mask, all pixels above knee would be
    compressed into a narrow band → gray plateau.
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
    Highlights must still get rolloff in postprocess after gamma.
    face_skin must NOT be in the rolloff mask — it passes through
    with natural variation even if slightly above knee.
    """
    # Simulate image with bright pixel at 215 (face_skin) and 230 (highlights)
    arr = np.full((10, 10), 100, dtype=np.uint8)
    arr[5, 5] = 215  # face_skin pixel (above knee after gamma)
    arr[5, 6] = 230  # highlights pixel (way above knee after gamma)
    img = Image.fromarray(arr, mode='L')

    subj = np.full((10, 10), 255, dtype=np.uint8)
    face = np.zeros((10, 10), dtype=np.uint8)

    hl = np.zeros((10, 10), dtype=np.uint8)
    hl[5, 6] = 255  # Only (5,6) is highlights
    fs = np.zeros((10, 10), dtype=np.uint8)
    fs[4:, :] = 255  # (5,5) is face_skin

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
    highlights_val = float(res[5, 6])

    # face_skin: NOT in rolloff mask → passes through (may be above knee)
    # After gamma: (215/255)^0.90 * 255 ≈ 218.7
    assert face_skin_val >= 218, (
        f"Face skin pixel {face_skin_val} should pass through "
        f"without rolloff compression"
    )

    # Highlights: IN rolloff mask → gets compressed
    # After gamma: (230/255)^0.90 * 255 ≈ 233.2, knee=216
    # Rolled off: 216 + (233.2-216)*0.35 = 216 + 6.0 = 222.0
    assert highlights_val < 225, (
        f"Highlights pixel {highlights_val} should be rolled off"
    )

    # face_skin should NOT be compressed — its value should be close to
    # the unrolled gamma value (≈218.7). Highlights got compressed but
    # still remain brighter because rolloff preserves the order.
    # The key test: face_skin is NOT compressed, so it maintains its
    # natural gamma-adjusted value (not squished down by rolloff).
    # face_skin at 218 should be well above what rolloff would produce
    # for a pixel at that pre-gamma level:
    # If face_skin were in rolloff mask: 216 + (218.7-216)*0.35 ≈ 217
    # Since face_skin is NOT in rolloff mask: ≈ 218.7 → 218 (uint8)
    # So we just verify face_skin is NOT compressed below its gamma value
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
