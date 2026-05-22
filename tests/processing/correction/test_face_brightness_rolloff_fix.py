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
