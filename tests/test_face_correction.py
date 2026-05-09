"""Тесты коррекции лица — маска, gentle_cap, детекция, face_mask.

Объединяет регрессионные тесты:
  - шов на овале лица (shrunk subject_mask вместо face_mask)
  - gentle_cap 1.08 вместо 1.15
  - регрессия детекции на нестандартных композициях
  - face_mask в check_face_brightness
"""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from retouch.processing.face_correction import (
    check_face_brightness,
    _curves_correction,
    _shrink_mask,
)
from retouch.processing.face_region import _detect_face_by_width_profile


# ─── Шов на овале лица ────────────────────────────────────────────────

class TestFaceCorrectionMask:
    """Коррекция по shrunk subject_mask, не face_mask."""

    def test_no_brightness_seam_at_face_boundary(self):
        """Нет скачка яркости на границе овала лица.

        Раньше _curves_correction применялся по face_mask (овал),
        создавая видимый шов. Теперь — shrunk subject_mask.
        """
        arr = np.full((200, 200), 80.0, dtype=np.float32)

        # face_mask — верхняя треть (овал лица)
        face_mask = np.zeros((200, 200), dtype=bool)
        face_mask[:70, 50:150] = True

        # shrunk_mask — весь субъект, сжатый от краёв
        shrunk_mask = np.zeros((200, 200), dtype=bool)
        shrunk_mask[5:195, 5:195] = True

        correction = 1.15

        result_shrunk = _curves_correction(
            arr, correction=correction, highlight_start=200,
            mask=shrunk_mask, target_ceiling=None)

        # Row 69 (внутри овала) vs row 71 (вне овала, но внутри субъекта)
        diff_inside = abs(result_shrunk[69, 100] - 80.0)
        diff_outside = abs(result_shrunk[71, 100] - 80.0)

        # Оба пикселя внутри shrunk_mask — коррекция одинаковая
        assert abs(diff_inside - diff_outside) < 5.0, \
            f"Скачок на границе овала: inside={diff_inside:.1f}, outside={diff_outside:.1f}"

    def test_correction_excludes_glow_border(self):
        """Маска коррекции исключает glow-зону (shrink на glow_size)."""
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle([50, 50, 149, 149], fill=255)

        shrunk = _shrink_mask(mask, shrink_px=10)
        original_white = (np.array(mask) > 128).sum()
        shrunk_white = (np.array(shrunk) > 128).sum()
        assert shrunk_white < original_white, \
            "Сжатая маска должна быть меньше оригинала"
        assert shrunk_white > 0, "Сжатая маска не должна быть пустой"


# ─── gentle_cap ────────────────────────────────────────────────────────

class TestGentleCap:
    """gentle_cap = 1.08 (было 1.15)."""

    def test_gentle_cap_108_when_p90_near_target(self):
        """p90 >= target_max - 15 — коррекция ограничена 1.08."""
        arr = np.full((200, 200), 130, dtype=np.uint8)
        arr[10:100, 10:100] = 195  # p90~195
        gray = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        target = [190, 210]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0)
        assert factor <= 1.08, \
            f"gentle_cap должен быть 1.08, factor={factor:.3f}"


# ─── Детекция лица ─────────────────────────────────────────────────────

class TestFaceDetectionRegression:
    """Регрессия детекции на нестандартных композициях."""

    def _make_mask_with_voluminous_hair(self, width=512, height=512):
        """Маска с объёмной причёской: широкий верх, узкие скулы."""
        mask = np.zeros((height, width), dtype=np.uint8)
        y, x = np.ogrid[:height, :width]
        cx = width // 2

        hair = ((x - cx) / 120) ** 2 + ((y - 100) / 60) ** 2 <= 1.0
        face = ((x - cx) / 70) ** 2 + ((y - 180) / 80) ** 2 <= 1.0
        shoulders = ((x - cx) / 150) ** 2 + ((y - 380) / 80) ** 2 <= 1.0

        subject = hair | face | shoulders
        mask[subject] = 255
        return Image.fromarray(mask)

    def test_voluminous_hair_face_not_displaced_up(self):
        """Объёмная причёска не смещает овал лица на макушку."""
        mask = self._make_mask_with_voluminous_hair()
        result = _detect_face_by_width_profile(mask, 512, 512)
        assert result is not None
        assert result["cy"] > 0.15, \
            f"Лицо не должно быть на макушке: cy={result['cy']:.2f}"

    def test_standard_portrait_still_works(self):
        """Стандартный портрет — детекция работает как раньше."""
        mask = np.zeros((512, 512), dtype=np.uint8)
        y, x = np.ogrid[:512, :512]
        cx = 256
        head = ((x - cx) / 80) ** 2 + ((y - 140) / 60) ** 2 <= 1.0
        shoulders = ((x - cx) / 150) ** 2 + ((y - 350) / 100) ** 2 <= 1.0
        mask[head | shoulders] = 255

        result = _detect_face_by_width_profile(
            Image.fromarray(mask), 512, 512)
        assert result is not None, "Стандартный портрет: лицо не найдено"
        assert result["cy"] < 0.5, "Лицо должно быть в верхней половине"


# ─── face_mask в check_face_brightness ─────────────────────────────────

class TestFaceMaskInCheckFaceBrightness:
    """face_mask_img используется для замера яркости в check_face_brightness."""

    def test_face_mask_img_overrides_face_region_top(self):
        """При передаче face_mask_img — замер по ней, не по face_region_top."""
        arr = np.full((300, 200), 200, dtype=np.uint8)
        arr[:100, :] = 50  # верхняя треть тёмная

        img = Image.fromarray(arr)
        subject_mask = Image.new("L", (200, 300), 255)

        face_mask_arr = np.zeros((300, 200), dtype=np.uint8)
        face_mask_arr[200:, :] = 255
        face_mask_img = Image.fromarray(face_mask_arr)

        _, before_with_mask, _, _ = check_face_brightness(
            img, [180, 220], subject_mask,
            face_mask_img=face_mask_img,
        )

        _, before_legacy, _, _ = check_face_brightness(
            img, [180, 220], subject_mask,
            face_region_top=0.45,
        )

        assert before_with_mask > before_legacy, \
            f"face_mask должен замерять по маске ({before_with_mask:.1f}), " \
            f"не по face_region_top ({before_legacy:.1f})"

    def test_face_mask_none_uses_legacy(self):
        """face_mask_img=None — legacy поведение (face_region_top)."""
        arr = np.full((200, 200), 150, dtype=np.uint8)
        img = Image.fromarray(arr)
        subject_mask = Image.new("L", (200, 200), 255)

        _, b1, _, _ = check_face_brightness(img, [180, 220], subject_mask, face_region_top=0.45)
        _, b2, _, _ = check_face_brightness(img, [180, 220], subject_mask, face_region_top=0.45, face_mask_img=None)

        assert b1 == b2
