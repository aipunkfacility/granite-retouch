"""Тесты shadow noise и shadow floor — шум в тенях субъекта.

Shadow noise: добавляет шум в тёмные пиксели субъекта (внутри маски),
чтобы при гравировке тени не «проваливались» в чёрную дыру.
Shadow floor: минимальная яркость для impact/laser, чтобы точки не
исчезали на камне.
"""

import copy
import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS


class TestShadowNoiseOnSubject:
    """Шум добавляется в тёмные пиксели субъекта, не на фоне."""

    def test_noise_in_subject_dark_pixels(self):
        """Шум добавляется в тёмные пиксели ВНУТРИ маски субъекта."""
        from retouch.processing.correction.levels import add_shadow_noise

        arr = np.zeros((200, 200), dtype=np.uint8)
        mask_arr = np.zeros((200, 200), dtype=np.uint8)
        mask_arr[:, :100] = 255
        arr[:, :100] = 0

        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)

        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15)
        result_arr = np.array(result)

        subject_dark = result_arr[:, :100][result_arr[:, :100] > 0]
        assert len(subject_dark) > 0, "Субъект должен получить шум"
        assert subject_dark.min() >= 5, f"Шум должен быть >= 5, got {subject_dark.min()}"

        bg_pixels = result_arr[:, 100:]
        assert bg_pixels.max() == 0, "Фон должен остаться 0 (без шума)"

    def test_noise_not_in_bright_subject_pixels(self):
        """Яркие пиксели субъекта (> threshold) НЕ получают шум."""
        from retouch.processing.correction.levels import add_shadow_noise

        arr = np.full((200, 200), 100, dtype=np.uint8)
        mask_arr = np.full((200, 200), 255, dtype=np.uint8)

        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)

        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15, shadow_threshold=30)
        result_arr = np.array(result)

        diff = np.abs(result_arr.astype(int) - 100)
        assert diff.max() == 0, "Яркие пиксели (> threshold) не должны получить шум"

    def test_shadow_threshold_parameter(self):
        """shadow_threshold контролирует, какие пиксели получают шум."""
        from retouch.processing.correction.levels import add_shadow_noise

        arr = np.zeros((200, 200), dtype=np.uint8)
        arr[:, :100] = 20   # тёмный (< threshold)
        arr[:, 100:] = 40   # средний (> threshold)

        mask_arr = np.full((200, 200), 255, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)

        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15, shadow_threshold=30)
        result_arr = np.array(result)

        dark_part = result_arr[:, :100]
        assert dark_part.min() >= 5, "Тёмная часть (<30) должна получить шум"

        mid_part = result_arr[:, 100:]
        assert mid_part.mean() == 40, "Средняя часть (>30) не должна измениться"

    def test_reproducible_with_seed(self):
        """Фиксированный seed = воспроизводимый результат."""
        from retouch.processing.correction.levels import add_shadow_noise

        arr = np.zeros((100, 100), dtype=np.uint8)
        mask_arr = np.full((100, 100), 255, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)

        result1 = add_shadow_noise(img, mask, noise_min=5, noise_max=15)
        result2 = add_shadow_noise(img, mask, noise_min=5, noise_max=15)

        assert np.array_equal(np.array(result1), np.array(result2)), \
            "Результат должен быть воспроизводимым с одним seed"


class TestShadowFloorImpact:
    """Shadow floor для impact — минимальная яркость субъекта."""

    def test_impact_shadow_floor_applied(self, tmp_path):
        """Impact: тёмные пиксели субъекта >= shadow_floor (до виньетки)."""
        from retouch.processing.core.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 10
        arr[ellipse, 1] = 8
        arr[ellipse, 2] = 6
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        config = copy.deepcopy(DEFAULTS)
        config["processing"]["impact"]["shadow_floor"] = 8

        result = process_steps(input_path, machine_type="impact", config=config)

        if result.subject_mask is not None and result.img_postproc is not None:
            postproc_arr = np.array(result.img_postproc)
            mask_bool = np.array(result.subject_mask) > 128
            subject_pixels = postproc_arr[mask_bool]
            below_floor = (subject_pixels < 8).sum()
            assert below_floor == 0, \
                f"Не должно быть пикселей < shadow_floor=8, found {below_floor}"

    def test_laser_no_shadow_floor(self, tmp_path):
        """Laser: shadow_floor не применяется (может быть 0)."""
        from retouch.processing.core.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)
        assert result.img_final is not None


class TestShadowFloorLaser:
    """Shadow floor для лазерных станков (SOP 5.1: black point 5-10)."""

    def test_laser_80w_has_shadow_floor(self):
        """Laser 80W: shadow_floor >= 5 в конфиге."""
        from retouch.config import load_config
        config = load_config()
        floor = config["processing"]["laser_80w"].get("shadow_floor", 0)
        assert floor >= 5, f"laser_80w shadow_floor должен быть >= 5, got {floor}"

    def test_laser_standard_has_shadow_floor(self):
        """Laser standard: shadow_floor >= 5 в конфиге."""
        from retouch.config import load_config
        config = load_config()
        floor = config["processing"]["laser_standard"].get("shadow_floor", 0)
        assert floor >= 5, f"laser_standard shadow_floor должен быть >= 5, got {floor}"

    def test_impact_shadow_floor_unchanged(self):
        """Impact: shadow_floor = 8 (не изменился)."""
        from retouch.config import load_config
        config = load_config()
        floor = config["processing"]["impact"].get("shadow_floor", 0)
        assert floor == 8, f"impact shadow_floor должен быть 8, got {floor}"

    def test_shadow_floor_applied_for_laser_80w(self, tmp_path):
        """Shadow_floor применяется для laser_80w в пайплайне."""
        from retouch.processing.core.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 10
        arr[ellipse, 1] = 8
        arr[ellipse, 2] = 6
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        config = copy.deepcopy(DEFAULTS)
        config["processing"]["laser_80w"]["shadow_floor"] = 5

        result = process_steps(input_path, machine_type="laser_80w", config=config)

        if result.subject_mask is not None and result.img_postproc is not None:
            postproc_arr = np.array(result.img_postproc)
            mask_bool = np.array(result.subject_mask) > 128
            subject_pixels = postproc_arr[mask_bool]
            below_floor = (subject_pixels < 5).sum()
            assert below_floor == 0, \
                f"Не должно быть пикселей < shadow_floor=5, found {below_floor}"


class TestShadowFloorInteraction:
    """REFACTOR-2: shadow_noise должен учитывать shadow_floor.

    Без фикса: шум генерируется в [5, 15], но shadow_floor=8
    перезапишет значения 5-7 до 8, стирая вариативность.
    """

    def test_noise_respects_shadow_floor(self):
        """Шум ниже shadow_floor бесполезен — floor его перезапишет.
        Поэтому шум должен генерироваться в диапазоне [max(noise_min, floor), noise_max]."""
        from retouch.processing.correction.shadow_noise import add_shadow_noise

        img = Image.new('L', (100, 100), 3)
        mask = Image.new('L', (100, 100), 255)
        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15,
                                  shadow_threshold=30, shadow_floor=8)
        arr = np.array(result)
        subject_pixels = arr[np.array(mask) > 128]
        assert subject_pixels.min() >= 8, (
            f"Шум ниже shadow_floor: min={subject_pixels.min()}, "
            f"floor=8 — эти значения будут перезаписаны"
        )

    def test_noise_floor_equals_noise_max_returns_unchanged(self):
        """shadow_floor >= noise_max — шум бессмысленен, изображение не меняется."""
        from retouch.processing.correction.shadow_noise import add_shadow_noise

        img = Image.new('L', (100, 100), 3)
        mask = Image.new('L', (100, 100), 255)
        result = add_shadow_noise(img, mask, noise_min=5, noise_max=8,
                                  shadow_threshold=30, shadow_floor=15)
        arr_result = np.array(result)
        arr_original = np.array(img)
        np.testing.assert_array_equal(arr_result, arr_original)

    def test_noise_without_floor_works_as_before(self):
        """Без shadow_floor (по умолчанию 0) — поведение не меняется."""
        from retouch.processing.correction.shadow_noise import add_shadow_noise

        img = Image.new('L', (100, 100), 3)
        mask = Image.new('L', (100, 100), 255)
        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15,
                                  shadow_threshold=30)
        arr = np.array(result)
        subject_pixels = arr[np.array(mask) > 128]
        assert subject_pixels.min() >= 5
        assert subject_pixels.max() <= 15

    def test_noise_floor_between_min_and_max(self):
        """shadow_floor между noise_min и noise_max — нижняя граница сдвигается."""
        from retouch.processing.correction.shadow_noise import add_shadow_noise

        img = Image.new('L', (100, 100), 3)
        mask = Image.new('L', (100, 100), 255)
        result = add_shadow_noise(img, mask, noise_min=3, noise_max=15,
                                  shadow_threshold=30, shadow_floor=8)
        arr = np.array(result)
        subject_pixels = arr[np.array(mask) > 128]
        assert subject_pixels.min() >= 8
        assert subject_pixels.max() <= 15
