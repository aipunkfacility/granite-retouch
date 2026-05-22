"""Test that Phase 1 lifted pixels get ceiling rolloff protection."""
import numpy as np
from PIL import Image

from retouch.processing.correction.face_brightness import face_brightness_correction
from retouch.processing.correction.postprocess import apply_postprocess


class _MockZM:
    """Minimal mock — only attributes face_brightness_correction reads."""
    def __init__(self, highlights, face_skin):
        self.highlights = highlights
        self.face_skin = face_skin


def test_rolloff_covers_phase1_lifted_pixels():
    """
    A face skin pixel below highlight_threshold gets boosted by Phase 1
    above knee. Without the fix it escapes (original highlights mask
    doesn't cover it). With the fix (apply_mask OR-ed in) it gets rolled off.
    """
    # 10x10 image: dark bg (80) + one bright skin pixel (175)
    img_arr = np.full((10, 10), 80, dtype=np.uint8)
    # highlight_threshold = 190 → 175 IS in face_skin (below threshold)
    # white_ceiling = 200 → knee = 180
    # Phase 1 boosts 175 above 180 → should be rolled off
    img_arr[5, 5] = 175
    img_gray = Image.fromarray(img_arr, mode='L')

    # Subject = whole image
    subj = np.full((10, 10), 255, dtype=np.uint8)
    subject_mask = Image.fromarray(subj, mode='L')

    # Face skin mask: bottom 6 rows (including our test pixel)
    face_skin = np.zeros((10, 10), dtype=np.uint8)
    face_skin[4:, :] = 255

    # Highlights zone: pixel (5,6) covered, pixel (5,5) NOT covered
    # (5,5) original 175 < 190 (highlight_threshold)
    hl = np.zeros((10, 10), dtype=np.uint8)
    hl[5, 6] = 255

    zm = _MockZM(hl, face_skin)

    cfg = {
        "face_brightness_target_min": 190,
        "face_brightness_target_max": 210,
        "white_ceiling": 200,          # knee = 180
        "rolloff_compression": 0.20,   # strong compression → visible difference
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
    lifted = float(arr[5, 5])   # Phase 1 boosted, NOT in original highlights
    ctrl = float(arr[5, 6])     # In original highlights → rolled off always

    # Without fix: 175 + 15*sqrt(175/255)=175+12.4=187.4. knee=180.
    #   Not in highlights → no rolloff → 187.4
    # With fix:    apply_mask OR-ed in → rolled off
    #   knee + excess*0.20 = 180 + 7.4*0.20 = 181.5
    # Set threshold between: 184
    assert lifted <= 184, (
        f"Lifted pixel {lifted} > 184 — not rolled off. "
        f"Phase 1 boosted it past knee but rolloff mask "
        f"(original highlights only) didn't cover it."
    )
    # Control pixel should always be rolled off
    assert ctrl <= 184, f"Control pixel {ctrl} should also be rolled off"


def test_postprocess_rolloff_covers_face_skin():
    """
    After gamma raises Phase 1 lifted pixels, apply_postprocess rolloff
    must also cover face_skin zone (not just original highlights).
    """
    # Simulate image AFTER face_brightness_correction + unsharp
    # Pixel at 215 was lifted by Phase 1 but not covered by original highlights
    # After gamma 0.90: (215/255)^0.90 * 255 ≈ 218.7 > knee 216 → needs rolloff
    arr = np.full((10, 10), 100, dtype=np.uint8)
    arr[5, 5] = 215
    img = Image.fromarray(arr, mode='L')

    subj = np.full((10, 10), 255, dtype=np.uint8)

    face = np.zeros((10, 10), dtype=np.uint8)

    # ZoneMasks: highlights cover (5,6) NOT (5,5); face_skin covers bottom 6 rows
    hl = np.zeros((10, 10), dtype=np.uint8)
    hl[5, 6] = 255
    fs = np.zeros((10, 10), dtype=np.uint8)
    fs[4:, :] = 255

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
    val = float(res[5, 5])

    # Without fix: 215 after gamma 0.90 → ~218.7 > knee 216, no rolloff → ~219
    # With fix:    face_skin included → rolls off to 216 + 2.7*0.35 ≈ 216.9
    assert val <= 217, (
        f"Pixel {val} > 217 — postprocess rolloff missing face_skin zone. "
        f"Gamma raised it above knee but original highlights mask "
        f"doesn't cover it."
    )
