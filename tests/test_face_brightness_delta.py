"""Тесты: delta возвращается из face_brightness_correction."""
import numpy as np
from PIL import Image

from retouch.processing.correction.face_brightness import face_brightness_correction


def test_face_brightness_delta_positive_when_too_dark():
    """Когда лицо темнее target — delta > 0."""
    img = Image.new("L", (100, 100), 100)
    mask = Image.new("L", (100, 100), 255)
    cfg = {
        "face_brightness_target_min": 180,
        "face_brightness_target_max": 220,
        "white_ceiling": 250,
        "rolloff_compression": 0.35,
    }
    analytics = {"median_brightness": 100.0, "p90_brightness": 120.0}
    _, before, after, factor, delta = face_brightness_correction(
        img, mask, None, cfg, analytics,
    )
    assert delta > 0.0, f"Expected positive delta, got {delta}"
    assert before > 0.0
    assert after > 0.0


def test_face_brightness_delta_negative_when_too_bright():
    """Когда лицо ярче target — delta < 0."""
    img = Image.new("L", (100, 100), 240)
    mask = Image.new("L", (100, 100), 255)
    cfg = {
        "face_brightness_target_min": 180,
        "face_brightness_target_max": 220,
        "white_ceiling": 250,
        "rolloff_compression": 0.35,
    }
    analytics = {"median_brightness": 240.0, "p90_brightness": 245.0}
    _, before, after, factor, delta = face_brightness_correction(
        img, mask, None, cfg, analytics,
    )
    assert delta < 0.0, f"Expected negative delta, got {delta}"
    assert before > 0.0
    assert after > 0.0


def test_face_brightness_delta_zero_within_target():
    """Когда лицо в target range — delta = 0."""
    img = Image.new("L", (100, 100), 200)
    mask = Image.new("L", (100, 100), 255)
    cfg = {
        "face_brightness_target_min": 180,
        "face_brightness_target_max": 220,
        "white_ceiling": 250,
        "rolloff_compression": 0.35,
    }
    analytics = {"median_brightness": 200.0, "p90_brightness": 205.0}
    _, before, after, factor, delta = face_brightness_correction(
        img, mask, None, cfg, analytics,
    )
    assert delta == 0.0, f"Expected delta=0, got {delta}"


def test_face_brightness_delta_max_clamped():
    """delta не превышает max_delta (15 по умолчанию)."""
    img = Image.new("L", (100, 100), 30)
    mask = Image.new("L", (100, 100), 255)
    cfg = {
        "face_brightness_target_min": 180,
        "face_brightness_target_max": 220,
        "white_ceiling": 250,
        "rolloff_compression": 0.35,
    }
    analytics = {"median_brightness": 30.0, "p90_brightness": 35.0}
    _, before, after, factor, delta = face_brightness_correction(
        img, mask, None, cfg, analytics,
    )
    # max_delta=15, target_min-median_before=150 → clamped to 15
    assert delta == 15.0, f"Expected delta=15 (clamped), got {delta}"


def test_face_brightness_delta_empty_mask():
    """Пустая маска: delta = 0."""
    img = Image.new("L", (100, 100), 100)
    mask = Image.new("L", (100, 100), 0)  # пустая маска
    cfg = {
        "face_brightness_target_min": 180,
        "face_brightness_target_max": 220,
        "white_ceiling": 250,
        "rolloff_compression": 0.35,
    }
    analytics = {"median_brightness": 100.0, "p90_brightness": 120.0}
    result, _, _, _, delta = face_brightness_correction(
        img, mask, None, cfg, analytics,
    )
    assert delta == 0.0, f"Expected delta=0 for empty mask, got {delta}"
    # Должен вернуть оригинал без изменений
    assert result is img
