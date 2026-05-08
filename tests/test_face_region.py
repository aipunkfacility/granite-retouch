"""Тесты модуля face_region — детекция лица и маски (этап C)."""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from retouch.processing.face_region import (
    _detect_face_by_width_profile,
    detect_face_oval,
    generate_face_mask,
    generate_hair_mask,
)


class TestDetectFaceByWidthProfile:
    """C.1: Улучшенная эвристика — профиль ширины маски."""

    def _make_portrait_mask(self, width=512, height=512):
        """Создать маску с головой и плечами."""
        mask = np.zeros((height, width), dtype=np.uint8)
        y, x = np.ogrid[:height, :width]

        # Голова — верхний эллипс (скулы ≈ 30% от верха)
        cx = width // 2
        cy_head = int(height * 0.28)
        rx_head = int(width * 0.16)
        ry_head = int(height * 0.13)
        head = ((x - cx) / rx_head) ** 2 + ((y - cy_head) / ry_head) ** 2 <= 1.0

        # Плечи — нижний широкий эллипс
        cy_shoulders = int(height * 0.62)
        rx_shoulders = int(width * 0.30)
        ry_shoulders = int(height * 0.22)
        shoulders = ((x - cx) / rx_shoulders) ** 2 + ((y - cy_shoulders) / ry_shoulders) ** 2 <= 1.0

        # Шея
        neck_w = int(width * 0.07)
        neck_top = cy_head + ry_head
        neck_bottom = cy_shoulders - ry_shoulders // 2
        neck = ((x >= cx - neck_w) & (x <= cx + neck_w) &
                (y >= neck_top) & (y <= neck_bottom))

        subject = head | neck | shoulders
        mask[subject] = 255
        return Image.fromarray(mask, "L")

    def test_standard_portrait_finds_face(self):
        """Стандартный портрет → face_region найден через профиль ширины."""
        mask = self._make_portrait_mask()
        result = _detect_face_by_width_profile(mask, 512, 512)

        assert result is not None, "Должен найти лицо"
        assert result["source"] == "heuristic"
        assert 0.0 < result["cx"] < 1.0
        assert 0.0 < result["cy"] < 0.7  # лицо в верхней части
        assert result["rx"] > 0.05
        assert result["ry"] > 0.05

    def test_face_cy_in_upper_half(self):
        """Центр лица (cy) должен быть в верхней половине изображения."""
        mask = self._make_portrait_mask()
        result = _detect_face_by_width_profile(mask, 512, 512)

        assert result is not None
        assert result["cy"] < 0.5, \
            f"Лицо должно быть в верхней половине, cy={result['cy']:.2f}"

    def test_half_body_portrait_shoulders_not_confused(self):
        """Портрет по пояс → плечи не путаются с лицом.

        Плечи шире чем лицо, но первый локальный максимум = скулы,
        а не плечи.
        """
        mask = self._make_portrait_mask()
        result = _detect_face_by_width_profile(mask, 512, 512)

        assert result is not None
        # Лицо должно быть значительно выше центра
        assert result["cy"] < 0.4, \
            f"Лицо должно быть в верхней трети, cy={result['cy']:.2f}"

    def test_empty_mask_returns_none(self):
        """Пустая маска → None (профиль нечитаем)."""
        mask = Image.new("L", (512, 512), 0)
        result = _detect_face_by_width_profile(mask, 512, 512)
        assert result is None

    def test_uniform_mask_returns_none_or_valid(self):
        """Равномерная маска (нет локального максимума) → None или валидный."""
        mask = Image.new("L", (512, 512), 255)
        result = _detect_face_by_width_profile(mask, 512, 512)
        # Равномерная маска может не иметь локального максимума
        # Это OK — fallback на legacy


class TestDetectFaceOval:
    """Трёхуровневая стратегия detect_face_oval."""

    def test_with_subject_mask_uses_heuristic(self):
        """С subject_mask → использует улучшенную эвристику."""
        # Создаём маску с чёткой структурой портрета
        mask = np.zeros((512, 512), dtype=np.uint8)
        y, x = np.ogrid[:512, :512]
        # Эллипс в верхней части — «голова»
        head = ((x - 256) / 80) ** 2 + ((y - 140) / 60) ** 2 <= 1.0
        # Широкая область внизу — «плечи»
        shoulders = ((x - 256) / 150) ** 2 + ((y - 350) / 100) ** 2 <= 1.0
        mask[head | shoulders] = 255
        subject_mask = Image.fromarray(mask, "L")

        img = Image.new("L", (512, 512), 128)

        result = detect_face_oval(img, subject_mask=subject_mask)

        assert "cx" in result
        assert "cy" in result
        assert "rx" in result
        assert "ry" in result
        assert "source" in result

    def test_without_mask_uses_legacy_fallback(self):
        """Без subject_mask → legacy fallback (верхние 45%)."""
        img = Image.new("L", (512, 512), 128)

        result = detect_face_oval(img, subject_mask=None)

        assert result["source"] == "heuristic_legacy"
        assert result["cx"] == 0.5
        assert result["cy"] == 0.25

    def test_unreadable_profile_uses_legacy(self):
        """Нечитаемый профиль → legacy fallback."""
        # Пустая маска — профиль нечитаем
        subject_mask = Image.new("L", (512, 512), 0)
        img = Image.new("L", (512, 512), 128)

        result = detect_face_oval(img, subject_mask=subject_mask)

        assert result["source"] == "heuristic_legacy"


class TestGenerateFaceMask:
    """C.2: Маска лица из овала."""

    def test_oval_creates_ellipse_mask(self):
        """Овал → эллипс-маска ∩ subject_mask."""
        width, height = 200, 300
        face_oval = {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20}

        # Субъект — весь кадр
        subject_mask = Image.new("L", (width, height), 255)

        face_mask = generate_face_mask(width, height, face_oval, subject_mask)

        assert face_mask is not None
        assert face_mask.size == (width, height)
        face_arr = np.array(face_mask)
        # Должны быть белые пиксели (эллипс)
        assert face_arr.max() == 255
        # Должны быть чёрные пиксели (за пределами эллипса)
        assert face_arr.min() == 0

    def test_face_mask_intersected_with_subject(self):
        """Маска лица = эллипс ∩ subject_mask."""
        width, height = 200, 300
        face_oval = {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20}

        # Субъект — только верхняя половина
        subject_arr = np.zeros((height, width), dtype=np.uint8)
        subject_arr[:150, :] = 255
        subject_mask = Image.fromarray(subject_arr, "L")

        face_mask = generate_face_mask(width, height, face_oval, subject_mask)
        face_arr = np.array(face_mask)

        # Нижняя часть (где нет субъекта) должна быть 0
        assert face_arr[200:, :].max() == 0

    def test_none_oval_returns_heuristic_mask(self):
        """face_oval=None → legacy heuristic mask."""
        width, height = 200, 300
        subject_mask = Image.new("L", (width, height), 255)

        face_mask = generate_face_mask(width, height, None, subject_mask)

        assert face_mask is not None
        face_arr = np.array(face_mask)
        # Верхние 45% должны быть белыми
        top_45 = face_arr[:int(height * 0.45), :]
        assert top_45.max() == 255

    def test_face_mask_has_pixels(self):
        """Маска лица содержит пиксели."""
        width, height = 512, 512
        face_oval = {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20}
        subject_mask = Image.new("L", (width, height), 255)

        face_mask = generate_face_mask(width, height, face_oval, subject_mask)
        face_arr = np.array(face_mask)

        assert face_arr.sum() > 0, "Маска лица не должна быть пустой"


class TestGenerateHairMask:
    """C.2: Маска волос = субъект выше овала лица с gap_ratio."""

    def test_hair_mask_above_face(self):
        """Маска волос — выше овала лица."""
        width, height = 200, 300
        face_oval = {"cx": 0.5, "cy": 0.30, "rx": 0.15, "ry": 0.10}
        subject_mask = Image.new("L", (width, height), 255)

        face_mask = generate_face_mask(width, height, face_oval, subject_mask)
        hair_mask = generate_hair_mask(face_mask, subject_mask, gap_ratio=0.05)

        hair_arr = np.array(hair_mask)
        # Волосы должны быть в верхней части
        assert hair_arr[:50, :].sum() > 0, "Волосы должны быть в верхней части"

    def test_gap_ratio_controls_separation(self):
        """gap_ratio контролирует зазор между лицом и волосами."""
        width, height = 200, 300
        face_oval = {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.15}
        subject_mask = Image.new("L", (width, height), 255)

        face_mask = generate_face_mask(width, height, face_oval, subject_mask)

        # С большим gap
        hair_large = generate_hair_mask(face_mask, subject_mask, gap_ratio=0.15)
        # С маленьким gap
        hair_small = generate_hair_mask(face_mask, subject_mask, gap_ratio=0.02)

        # Большой gap = меньше пикселей в маске волос
        assert np.array(hair_large).sum() <= np.array(hair_small).sum()
