"""Тесты Фазы 2 — Восстановление качества (FIX #4, #5, #6, #7).

FIX #4: face_correction mask — shrunk subject_mask вместо face_mask
FIX #5: gentle_cap 1.08 вместо 1.15
FIX #6: face detection — комбинированная эвристика
FIX #7: clamp_masked vmin=0 по умолчанию
"""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from retouch.processing.face_correction import (
    check_face_brightness,
    _curves_correction,
    _shrink_mask,
)
from retouch.processing.mask_utils import clamp_masked
from retouch.processing.face_region import _detect_face_by_width_profile


# ─── FIX #4: Шов на овале лица ────────────────────────────────────────

class TestFaceCorrectionMask:
    """FIX #4: коррекция по shrunk subject_mask, не face_mask."""

    def test_no_brightness_seam_at_face_boundary(self):
        """Нет скачка яркости на границе овала лица.

        Старый баг: _curves_correction применялся по face_mask (овал),
        создавая видимый шов. Новый код: shrunk subject_mask.
        """
        # Синтетический случай: лицо=80, воротник=80 (одинаковая яркость)
        arr = np.full((200, 200), 80.0, dtype=np.float32)

        # face_mask — верхняя треть (овал лица)
        face_mask = np.zeros((200, 200), dtype=bool)
        face_mask[:70, 50:150] = True

        # shrunk subject_mask — весь субъект, сжатый от краёв
        shrunk_mask = np.zeros((200, 200), dtype=bool)
        shrunk_mask[5:195, 5:195] = True

        correction = 1.15

        # Со shrunk_mask: весь субъект корректируется равномерно
        result_shrunk = _curves_correction(
            arr, correction=correction, highlight_start=200,
            mask=shrunk_mask, target_ceiling=None)

        # На границе овала (row 70, col 100) — скачок при face_mask
        # При shrunk_mask — скачок минимальный (весь субъект корректируется)
        # Row 69 (внутри овала) vs row 71 (вне овала, но внутри субъекта)
        diff_inside = abs(result_shrunk[69, 100] - 80.0)
        diff_outside = abs(result_shrunk[71, 100] - 80.0)

        # Оба пикселя должны получить примерно одинаковую коррекцию
        # (оба внутри shrunk_mask)
        assert abs(diff_inside - diff_outside) < 5.0, \
            f"Скачок на границе овала: inside={diff_inside:.1f}, outside={diff_outside:.1f}"

    def test_correction_excludes_glow_border(self):
        """Маска коррекции исключает glow-зону (shrink на glow_size)."""
        # Субъект — квадрат 100x100 в центре
        mask = Image.new("L", (200, 200), 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle([50, 50, 149, 149], fill=255)

        # Glow size = 10px — маска должна сжаться на 10px
        shrunk = _shrink_mask(mask, shrink_px=10)
        original_white = (np.array(mask) > 128).sum()
        shrunk_white = (np.array(shrunk) > 128).sum()
        assert shrunk_white < original_white, \
            "Сжатая маска должна быть меньше оригинала"
        assert shrunk_white > 0, "Сжатая маска не должна быть пустой"


# ─── FIX #5: gentle_cap 1.08 ──────────────────────────────────────────

class TestGentleCap:
    """FIX #5: gentle_cap = 1.08 (было 1.15)."""

    def test_gentle_cap_108_when_p90_near_target(self):
        """p90 >= target_max - 15 → коррекция ограничена 1.08."""
        # Создаём лицо с median=130, p90≈195 (target_max=210, target_max-15=195)
        # Нужно достаточно ярких пикселей чтобы p90 дошел до 195
        arr = np.full((200, 200), 130, dtype=np.uint8)
        # Большая область с яркими пикселями для высокого p90
        arr[10:100, 10:100] = 195  # 90x90 = 8100 пикселей из 40000 → p90≈195
        gray = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        target = [190, 210]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0)
        # Коррекция должна быть <= 1.08 (gentle_cap)
        assert factor <= 1.08, \
            f"gentle_cap должен быть 1.08, factor={factor:.3f}"


# ─── FIX #6: Детекция лица ────────────────────────────────────────────

class TestFaceDetectionRegression:
    """FIX #6: регрессия детекции на нестандартных композициях."""

    def _make_mask_with_voluminous_hair(self, width=512, height=512):
        """Маска с объёмной причёской: широкий верх, узкие скулы."""
        mask = np.zeros((height, width), dtype=np.uint8)
        y, x = np.ogrid[:height, :width]
        cx = width // 2

        # Объёмная причёска — широкий эллипс вверху (шире скул)
        hair = ((x - cx) / 120) ** 2 + ((y - 100) / 60) ** 2 <= 1.0
        # Лицо — уже (скулы)
        face = ((x - cx) / 70) ** 2 + ((y - 180) / 80) ** 2 <= 1.0
        # Плечи
        shoulders = ((x - cx) / 150) ** 2 + ((y - 380) / 80) ** 2 <= 1.0

        subject = hair | face | shoulders
        mask[subject] = 255
        return Image.fromarray(mask)

    def test_voluminous_hair_face_not_displaced_up(self):
        """Объёмная причёска не смещает овал лица на макушку."""
        mask = self._make_mask_with_voluminous_hair()
        result = _detect_face_by_width_profile(mask, 512, 512)
        assert result is not None
        # cy должен быть ниже 0.15 (не на макушке)
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


# ─── FIX #7: clamp_masked vmin ────────────────────────────────────────

class TestClampMaskedVmin:
    """FIX #7: clamp_masked клиппит отрицательные значения."""

    def test_clamp_masked_clips_negative(self):
        """Отрицательные значения обрезаются до vmin=0."""
        arr = np.array([[-10, -1, 50, 200, 300]], dtype=np.float32)
        mask = Image.new("L", (5, 1), 255)
        result = clamp_masked(arr, mask, vmin=0, vmax=255)
        assert result.min() >= 0, f"Отрицательные не обрезаны: min={result.min()}"

    def test_clamp_masked_default_vmin_is_zero(self):
        """По умолчанию vmin=0 (не None)."""
        arr = np.array([[-5, 100, 260]], dtype=np.float32)
        mask = Image.new("L", (3, 1), 255)
        result = clamp_masked(arr.reshape(1, 3), mask, vmax=250)
        assert result.flatten()[0] >= 0, "vmin=0 по умолчанию"

    def test_clamp_masked_outside_mask_unchanged(self):
        """Пиксели вне маски не меняются."""
        arr = np.array([[-10, 100, 300]], dtype=np.float32)
        # Маска — только средний пиксель
        mask_arr = np.array([[0, 255, 0]], dtype=np.uint8)
        mask = Image.fromarray(mask_arr)
        result = clamp_masked(arr.reshape(1, 3), mask, vmin=0, vmax=250)
        flat = result.flatten()
        assert flat[0] == -10.0, "Фон не должен меняться (vmin)"
        assert flat[2] == 300.0, "Фон не должен меняться (vmax)"
        assert flat[1] == 100.0, "Субъект в диапазоне — не меняется"
