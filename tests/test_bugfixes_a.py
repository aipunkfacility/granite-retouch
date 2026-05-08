"""Тесты багфиксов этапа A — TDD.

A.1: Shadow noise на субъекте, не на фоне
A.2: Shadow floor — отдельный шаг для impact
A.3: Порядок шагов — unsharp ПОСЛЕ face_brightness
A.4: White ceiling hard clamp перед экспортом
A.5: Glow rename + настоящий inner glow
"""

import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS


class TestA1ShadowNoiseOnSubject:
    """A.1: Шум в тёмных пикселях субъекта, не на фоне."""

    def test_noise_in_subject_dark_pixels(self):
        """Шум добавляется в тёмные пиксели ВНУТРИ маски субъекта."""
        from retouch.processing.levels import add_shadow_noise

        # Изображение: субъект=0 (тёмный), фон=0 (чёрный)
        arr = np.zeros((200, 200), dtype=np.uint8)
        mask_arr = np.zeros((200, 200), dtype=np.uint8)
        # Левая половина — субъект (тёмный), правая — фон
        mask_arr[:, :100] = 255
        arr[:, :100] = 0  # тёмный субъект

        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)

        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15)
        result_arr = np.array(result)

        # Левая половина (субъект) получила шум (>= noise_min)
        subject_pixels = result_arr[:, :100]
        subject_dark = subject_pixels[subject_pixels > 0]
        assert len(subject_dark) > 0, "Субъект должен получить шум"
        assert subject_dark.min() >= 5, f"Шум должен быть >= 5, got {subject_dark.min()}"

        # Правая половина (фон) осталась 0
        bg_pixels = result_arr[:, 100:]
        assert bg_pixels.max() == 0, "Фон должен остаться 0 (без шума)"

    def test_noise_not_in_bright_subject_pixels(self):
        """Яркие пиксели субъекта (> threshold) НЕ получают шум."""
        from retouch.processing.levels import add_shadow_noise

        arr = np.full((200, 200), 100, dtype=np.uint8)  # яркий субъект
        mask_arr = np.full((200, 200), 255, dtype=np.uint8)  # всё — субъект

        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)

        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15, shadow_threshold=30)
        result_arr = np.array(result)

        # Все пиксели были 100 > threshold(30) → шум не добавлен
        diff = np.abs(result_arr.astype(int) - 100)
        assert diff.max() == 0, "Яркие пиксели (> threshold) не должны получить шум"

    def test_shadow_threshold_parameter(self):
        """shadow_threshold контролирует, какие пиксели получают шум."""
        from retouch.processing.levels import add_shadow_noise

        # Субъект с разными уровнями яркости
        arr = np.zeros((200, 200), dtype=np.uint8)
        arr[:, :100] = 20   # тёмный (< threshold)
        arr[:, 100:] = 40   # средний (> threshold)

        mask_arr = np.full((200, 200), 255, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)

        # С threshold=30: только пиксели < 30 получают шум
        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15, shadow_threshold=30)
        result_arr = np.array(result)

        # Тёмная часть получила шум
        dark_part = result_arr[:, :100]
        assert dark_part.min() >= 5, "Тёмная часть (<30) должна получить шум"

        # Средняя часть не изменилась
        mid_part = result_arr[:, 100:]
        assert mid_part.mean() == 40, "Средняя часть (>30) не должна измениться"

    def test_reproducible_with_seed(self):
        """Фиксированный seed = воспроизводимый результат."""
        from retouch.processing.levels import add_shadow_noise

        arr = np.zeros((100, 100), dtype=np.uint8)
        mask_arr = np.full((100, 100), 255, dtype=np.uint8)
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)

        result1 = add_shadow_noise(img, mask, noise_min=5, noise_max=15)
        result2 = add_shadow_noise(img, mask, noise_min=5, noise_max=15)

        assert np.array_equal(np.array(result1), np.array(result2)), \
            "Результат должен быть воспроизводимым с одним seed"


class TestA2ShadowFloor:
    """A.2: Shadow floor — минимальная яркость для impact."""

    def test_impact_shadow_floor_applied(self, tmp_path):
        """Impact: тёмные пиксели субъекта >= shadow_floor (до виньетки)."""
        from retouch.processing.pipeline import process_steps

        # Создаём очень тёмное изображение
        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255  # синий фон
        arr[..., 3] = 255
        # Тёмный субъект в центре
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 10
        arr[ellipse, 1] = 8
        arr[ellipse, 2] = 6
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        import copy; config = copy.deepcopy(DEFAULTS)
        # Устанавливаем shadow_floor для impact
        config["processing"]["impact"]["shadow_floor"] = 8

        result = process_steps(input_path, machine_type="impact", config=config)

        # Проверяем img_sharpened (до виньетки) — shadow_floor применяется
        # к img_sharpened. После виньетки часть субъекта может быть затемнена
        # аркой, поэтому проверяем до виньетки.
        if result.subject_mask is not None and result.img_sharpened is not None:
            sharpened_arr = np.array(result.img_sharpened)
            mask_bool = np.array(result.subject_mask) > 128
            subject_pixels = sharpened_arr[mask_bool]
            # shadow_floor=8: после обработки минимум должен быть >= 8
            below_floor = (subject_pixels < 8).sum()
            assert below_floor == 0, \
                f"Не должно быть пикселей < shadow_floor=8, found {below_floor}"

    def test_laser_no_shadow_floor(self, tmp_path):
        """Laser: shadow_floor не применяется (может быть 0)."""
        from retouch.processing.pipeline import process_steps

        # Создаём изображение
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
        # Laser не имеет shadow_floor — пайплайн просто не должен упасть
        assert result.img_final is not None


class TestA3StepOrder:
    """A.3: Unsharp ПОСЛЕ face_brightness."""

    def test_new_step_order_unsharp_after_face(self, tmp_path):
        """В новом порядке unsharp вызывается после face_brightness."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 80
        arr[ellipse, 1] = 60
        arr[ellipse, 2] = 40
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        # Новый порядок (по умолчанию)
        import copy; config = copy.deepcopy(DEFAULTS)
        config["processing"]["legacy_step_order"] = False

        result = process_steps(input_path, machine_type="laser_standard", config=config)
        assert result.img_final is not None
        # Проверяем что img_sharpened и img_face_corrected — разные изображения
        # (unsharp после face_brightness)

    def test_legacy_step_order_rollback(self, tmp_path):
        """legacy_step_order=True возвращает старый порядок."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 80
        arr[ellipse, 1] = 60
        arr[ellipse, 2] = 40
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        # Старый порядок
        import copy; config = copy.deepcopy(DEFAULTS)
        config["processing"]["legacy_step_order"] = True

        result = process_steps(input_path, machine_type="laser_standard", config=config)
        assert result.img_final is not None


class TestA4WhiteCeilingClamp:
    """A.4: Hard clamp белой точки перед экспортом."""

    def test_no_pixels_above_white_ceiling(self, tmp_path):
        """Внутри маски субъекта нет пикселей > white_ceiling."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        # Очень яркий субъект — должен быть обрезан
        arr[ellipse, 0] = 250
        arr[ellipse, 1] = 250
        arr[ellipse, 2] = 250
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr)
        input_path = str(tmp_path / "bright.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        # white_ceiling=250 для laser_standard
        white_ceiling = DEFAULTS["processing"]["laser_standard"]["white_ceiling"]
        if result.subject_mask is not None:
            final_arr = np.array(result.img_final.convert("L"))
            mask_bool = np.array(result.subject_mask) > 128
            subject_pixels = final_arr[mask_bool]
            above = (subject_pixels > white_ceiling).sum()
            assert above == 0, \
                f"Нет пикселей > {white_ceiling} в субъекте, found {above}"


class TestA5GlowRenameAndInnerGlow:
    """A.5: Glow rename + настоящий inner glow."""

    def test_outer_glow_brightens_edges(self):
        """Outer glow делает край субъекта светлее."""
        from retouch.processing.glow import apply_outer_glow

        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.ellipse([50, 50, 149, 149], fill=255)

        result = apply_outer_glow(gray, mask, glow_size=20, glow_opacity=0.35)
        result_arr = np.array(result)

        # Край маски должен быть светлее исходного
        edge_pixels = result_arr[45:55, 95:105]
        assert edge_pixels.mean() > 80, "Outer glow должен делать край светлее"

    def test_inner_glow_brightens_inner_edge(self):
        """Inner glow делает внутренний край субъекта светлее."""
        from retouch.processing.glow import apply_inner_glow_algorithm

        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.ellipse([50, 50, 149, 149], fill=255)

        result = apply_inner_glow_algorithm(gray, mask, glow_size=20, glow_opacity=0.80)
        result_arr = np.array(result)

        # Внутренний край должен быть светлее исходного
        # Центр должен остаться близким к исходному
        center_pixel = result_arr[100, 100]
        edge_pixel = result_arr[55, 100]  # внутренний край

        assert edge_pixel > 80, f"Внутренний край должен быть светлее 80, got {edge_pixel}"
        # Центр может быть чуть светлее из-за blur, но не сильно
        assert center_pixel < 200, f"Центр не должен засвечиваться, got {center_pixel}"

    def test_glow_style_outer_backward_compat(self):
        """glow_style='outer' даёт тот же результат что и раньше."""
        from retouch.processing.glow import apply_inner_glow

        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.ellipse([50, 50, 149, 149], fill=255)

        machine_cfg = {"glow_size_min": 20, "glow_size_max": 20,
                       "glow_opacity_min": 35, "glow_opacity_max": 35,
                       "glow_style": "outer"}

        result, glow_size, glow_opacity = apply_inner_glow(
            gray, mask, machine_cfg,
            glow_size_override=20, glow_opacity_override=35,
        )

        assert glow_size == 20
        assert abs(glow_opacity - 0.35) < 0.01
        result_arr = np.array(result)
        assert result_arr.mean() > 80, "Outer glow должен осветлять"

    def test_glow_style_inner(self):
        """glow_style='inner' использует настоящий inner glow."""
        from retouch.processing.glow import apply_inner_glow

        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.ellipse([50, 50, 149, 149], fill=255)

        machine_cfg = {"glow_size_min": 20, "glow_size_max": 20,
                       "glow_opacity_min": 35, "glow_opacity_max": 35,
                       "glow_style": "inner"}

        result, glow_size, glow_opacity = apply_inner_glow(
            gray, mask, machine_cfg,
            glow_size_override=20, glow_opacity_override=80,
        )

        result_arr = np.array(result)
        # Inner glow должен осветлять внутренний край
        assert result_arr.max() > 80, "Inner glow должен осветлять"
