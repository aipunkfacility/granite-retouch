"""Single rolloff: face_brightness_no_ceiling → apply_postprocess catches all."""
import numpy as np
from PIL import Image

from retouch.processing.correction.face_brightness import face_brightness_correction
from retouch.processing.correction.postprocess import apply_postprocess


def test_face_brightness_no_longer_ceils():
    """Phase 3 rolloff removed: pixels above ceiling stay untouched."""
    img_arr = np.full((10, 10), 100, dtype=np.uint8)
    img_arr[5, 5] = 230
    img_gray = Image.fromarray(img_arr, mode='L')
    subj = Image.fromarray(np.full((10, 10), 255, dtype=np.uint8), mode='L')
    face_skin = np.full((10, 10), 255, dtype=np.uint8)

    result, *_ = face_brightness_correction(
        img_gray=img_gray,
        subject_mask=subj,
        face_skin_mask=face_skin,
        machine_cfg={
            "face_brightness_target_min": 80,
            "face_brightness_target_max": 120,
            "white_ceiling": 200,
            "rolloff_compression": 0.35,
        },
        analytics={"median_brightness": 100, "p90_brightness": 110},
    )
    arr = np.array(result)
    assert arr[5, 5] > 200, "face_brightness should NOT ceiling (rolloff removed)"


def test_postprocess_rolloff_full_subject():
    """apply_postprocess rolls off ALL subject pixels, not just zone masks."""
    arr = np.full((10, 10), 100, dtype=np.uint8)
    arr[5, 5] = 215
    img = Image.fromarray(arr, mode='L')
    subj = np.full((10, 10), 255, dtype=np.uint8)
    face = np.zeros((10, 10), dtype=np.uint8)

    result = apply_postprocess(
        img=img,
        subject_mask=subj,
        face_mask=face,
        machine_type="impact",
        shadow_floor=0,
        stone_gamma=0.90,
        white_ceiling=240,
        compression=0.35,
    )
    res = np.array(result)
    val = float(res[5, 5])

    # knee=216, excess ≈ 2.7, rolloff = 216 + 2.7*0.35 ≈ 216.9
    assert val <= 217, (
        f"Pixel {val} > 217 — postprocess full-subject rolloff didn't catch it. "
        f"Gamma raised it above knee but rolloff missed it."
    )


def test_bg_not_affected_by_rolloff():
    """Background pixels outside subject_mask are NOT rolled off."""
    arr = np.full((10, 10), 100, dtype=np.uint8)
    arr[5, 5] = 230
    img = Image.fromarray(arr, mode='L')

    subj = np.zeros((10, 10), dtype=np.uint8)
    subj[2:8, 2:8] = 255

    result = apply_postprocess(
        img=img,
        subject_mask=subj,
        face_mask=None,
        machine_type="impact",
        shadow_floor=0,
        stone_gamma=None,
        white_ceiling=200,
        compression=0.20,
    )
    res = np.array(result)
    # bg pixel (0,0) untouched
    assert res[0, 0] == 100, "Background must not be rolled off"


def test_impact_preset_no_gray_plateau(include_unsharp=True):
    """
    End-to-end: Mirtels/Stonegraf/Sauno impact preset values should NOT
    produce a gray plateau on face skin.

    Simulates the full correction chain:
    face_brightness -> [unsharp] -> gamma -> rolloff

    With gamma-aware target (Level 1) + safety cap (Level 2),
    face_skin should maintain >25 tonal levels after the full chain,
    INCLUDING unsharp mask overshoot.
    """
    rng = np.random.RandomState(42)
    arr = rng.normal(loc=165, scale=30, size=(100, 100)).astype(np.float32)
    arr[10:30, 30:70] = np.clip(arr[10:30, 30:70] + 40, 0, 245)
    arr = np.clip(arr, 50, 245).astype(np.uint8)
    img_gray = Image.fromarray(arr, mode='L')

    subj = np.full((100, 100), 255, dtype=np.uint8)
    subject_mask = Image.fromarray(subj, mode='L')

    face_skin = np.zeros((100, 100), dtype=np.uint8)
    face_skin[40:, :] = 255

    cfg = {
        "face_brightness_target_min": 200,
        "face_brightness_target_max": 225,
        "stone_gamma": 0.90,
        "white_ceiling": 240,
        "rolloff_compression": 0.35,
    }
    analytics = {"median_brightness": 165.0, "p90_brightness": 210.0}

    result_fb, _, _, _, _ = face_brightness_correction(
        img_gray=img_gray,
        subject_mask=subject_mask,
        face_skin_mask=face_skin,
        machine_cfg=cfg,
        analytics=analytics,
    )

    if include_unsharp:
        from retouch.processing.correction.unsharp import apply_unsharp_mask
        result_unsharp = apply_unsharp_mask(
            result_fb,
            radius=1.5,
            percent=120,
            threshold=0,
            subject_mask=subject_mask,
            analytics=analytics,
        )
    else:
        result_unsharp = result_fb

    gamma = 0.90
    ceiling = 240.0
    knee = ceiling * 0.90
    max_pre_gamma = np.power(knee / 255.0, 1.0 / gamma) * 255.0
    cap_arr = np.array(result_unsharp, dtype=np.float32)
    fs_bool = face_skin > 128
    cap_arr[fs_bool] = np.minimum(cap_arr[fs_bool], max_pre_gamma)
    result_capped = Image.fromarray(np.clip(cap_arr, 0, 255).astype(np.uint8), mode='L')

    result_final = apply_postprocess(
        img=result_capped,
        subject_mask=subj,
        face_mask=np.zeros((100, 100), dtype=np.uint8),
        machine_type="impact",
        shadow_floor=8,
        stone_gamma=0.90,
        white_ceiling=240,
        compression=0.35,
    )

    final_arr = np.array(result_final, dtype=np.float32)
    face_pixels = final_arr[fs_bool]
    p10, p90 = np.percentile(face_pixels, [10, 90])
    tonal_range = p90 - p10

    assert tonal_range > 25, (
        f"Face skin tonal range after full pipeline (unsharp={'yes' if include_unsharp else 'no'}): "
        f"{tonal_range:.1f} (p10={p10:.1f}, p90={p90:.1f}). "
        f"Expected >25 — gamma-aware target + safety cap should prevent plateau."
    )

    non_face = final_arr[~fs_bool & (subj > 128)]
    if len(non_face) > 0:
        face_max = float(np.percentile(face_pixels, 95))
        non_face_max = float(np.percentile(non_face, 95))
        assert face_max <= non_face_max + 3, (
            f"Tonal inversion: face_skin p95={face_max:.1f} > "
            f"non-face p95={non_face_max:.1f} + 3. "
            f"Face should not be brighter than highlights."
        )


def test_impact_preset_no_gray_plateau_without_unsharp():
    """Same test but skipping unsharp — verifies Level 1 alone is sufficient
    when no unsharp overshoot is present."""
    test_impact_preset_no_gray_plateau(include_unsharp=False)


def test_impact_preset_no_gray_plateau_with_unsharp():
    """Full pipeline with unsharp mask — proves safety cap (Level 2) catches
    unsharp overshoot and prevents plateau even with +5-15 level boost."""
    test_impact_preset_no_gray_plateau(include_unsharp=True)
