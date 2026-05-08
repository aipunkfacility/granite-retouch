"""Регрессионные тесты этапа G.

G.1: P0 регрессия (багфиксы)
G.2: P1 функциональные тесты
G.3: Интеграционный тест
"""

import os
import numpy as np
import pytest
from PIL import Image

from retouch.config import DEFAULTS


class TestG1P0Regression:
    """G.1: P0 регрессионные тесты."""

    def test_shadow_noise_subject_not_background(self):
        """Shadow noise: шум в субъекте, не на фоне."""
        from retouch.processing.levels import add_shadow_noise

        arr = np.zeros((200, 200), dtype=np.uint8)
        mask_arr = np.zeros((200, 200), dtype=np.uint8)
        # Субъект — левая половина, тёмный
        mask_arr[:, :100] = 255
        arr[:, :100] = 0

        img = Image.fromarray(arr, "L")
        mask = Image.fromarray(mask_arr, "L")

        result = add_shadow_noise(img, mask, noise_min=5, noise_max=15)
        result_arr = np.array(result)

        # Фон остался 0
        assert result_arr[:, 100:].max() == 0
        # Субъект получил шум
        assert result_arr[:, :100].min() >= 5

    def test_shadow_floor_impact(self, tmp_path):
        """Shadow floor: impact → нет < floor в субъекте (до виньетки)."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 10
        arr[ellipse, 1] = 8
        arr[ellipse, 2] = 6
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr, "RGBA")
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        import copy; config = copy.deepcopy(DEFAULTS)
        result = process_steps(input_path, machine_type="impact", config=config)

        # Проверяем img_sharpened (до виньетки)
        if result.subject_mask is not None and result.img_sharpened is not None:
            sharpened_arr = np.array(result.img_sharpened)
            mask_bool = np.array(result.subject_mask) > 128
            subject_pixels = sharpened_arr[mask_bool]
            shadow_floor = config["processing"]["impact"].get("shadow_floor", 8)
            below = (subject_pixels < shadow_floor).sum()
            assert below == 0, f"Пиксели < {shadow_floor}: {below}"

    def test_step_order_unsharp_after_face(self, tmp_path):
        """Порядок шагов: unsharp после face_brightness (новый порядок)."""
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

        img = Image.fromarray(arr, "RGBA")
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        import copy; config = copy.deepcopy(DEFAULTS)
        config["processing"]["legacy_step_order"] = False

        result = process_steps(input_path, machine_type="laser_standard", config=config)
        assert result.img_final is not None
        # img_sharpened и img_face_corrected — разные объекты
        assert result.img_sharpened is not result.img_face_corrected

    def test_white_ceiling_clamp(self, tmp_path):
        """White ceiling: нет пикселей > white_ceiling в субъекте."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 250
        arr[ellipse, 1] = 250
        arr[ellipse, 2] = 250
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr, "RGBA")
        input_path = str(tmp_path / "bright.png")
        img.save(input_path, "PNG")

        result = process_steps(input_path, machine_type="laser_standard", config=DEFAULTS)

        white_ceiling = DEFAULTS["processing"]["laser_standard"]["white_ceiling"]
        if result.subject_mask is not None:
            final_arr = np.array(result.img_final.convert("L"))
            mask_bool = np.array(result.subject_mask) > 128
            subject_pixels = final_arr[mask_bool]
            above = (subject_pixels > white_ceiling).sum()
            assert above == 0, f"Пиксели > {white_ceiling}: {above}"


class TestG2P1Functional:
    """G.2: P1 функциональные тесты."""

    def test_inner_glow_shrink_edge_blur(self):
        """Inner glow: shrink→edge→blur = свечение внутрь."""
        from retouch.processing.glow import apply_inner_glow_algorithm

        gray = Image.new("L", (200, 200), 60)
        mask = Image.new("L", (200, 200), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([40, 40, 159, 159], fill=255)

        result = apply_inner_glow_algorithm(gray, mask, glow_size=20, glow_opacity=0.80)
        result_arr = np.array(result)

        # Внутренний край должен быть светлее
        edge = result_arr[42:48, 42:48]  # внутренний край
        center = result_arr[90:110, 90:110]  # центр

        assert edge.mean() > center.mean(), \
            "Внутренний край должен быть светлее центра"

    def test_outer_glow(self):
        """Outer glow: свечение наружу."""
        from retouch.processing.glow import apply_outer_glow

        gray = Image.new("L", (200, 200), 60)
        mask = Image.new("L", (200, 200), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([60, 60, 139, 139], fill=255)

        result = apply_outer_glow(gray, mask, glow_size=20, glow_opacity=0.50)
        result_arr = np.array(result)

        # Края субъекта должны быть светлее фона
        edge = result_arr[55:65, 55:65]
        assert edge.mean() > 60, "Край должен быть светлее фона"

    def test_face_mask_oval_intersect_subject(self):
        """generate_face_mask: овал ∩ subject_mask."""
        from retouch.processing.face_region import generate_face_mask

        width, height = 200, 300
        face_oval = {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20}

        # Субъект — весь кадр
        subject_mask = Image.new("L", (width, height), 255)
        face_mask = generate_face_mask(width, height, face_oval, subject_mask)

        face_arr = np.array(face_mask)
        # Должен быть эллипс в верхней части
        top_half = face_arr[:150, :]
        bottom_half = face_arr[150:, :]
        assert top_half.sum() > bottom_half.sum()

    def test_hair_mask_above_face(self):
        """generate_hair_mask: выше овала + gap_ratio."""
        from retouch.processing.face_region import generate_face_mask, generate_hair_mask

        width, height = 200, 300
        face_oval = {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.15}
        subject_mask = Image.new("L", (width, height), 255)

        face_mask = generate_face_mask(width, height, face_oval, subject_mask)
        hair_mask = generate_hair_mask(face_mask, subject_mask, gap_ratio=0.05)

        hair_arr = np.array(hair_mask)
        # Волосы должны быть выше центра
        top_quarter = hair_arr[:75, :]
        bottom = hair_arr[200:, :]
        assert top_quarter.sum() >= bottom.sum()

    def test_width_profile_detects_face(self):
        """Профиль ширины маски → face_region найден."""
        from retouch.processing.face_region import detect_face_oval

        # Маска с головой и плечами
        mask = np.zeros((512, 512), dtype=np.uint8)
        y, x = np.ogrid[:512, :512]
        head = ((x - 256) / 80) ** 2 + ((y - 140) / 60) ** 2 <= 1.0
        shoulders = ((x - 256) / 150) ** 2 + ((y - 350) / 100) ** 2 <= 1.0
        mask[head | shoulders] = 255
        subject_mask = Image.fromarray(mask, "L")

        img = Image.new("L", (512, 512), 128)
        result = detect_face_oval(img, subject_mask=subject_mask)

        assert result is not None
        assert result["cy"] < 0.5, f"Лицо должно быть в верхней части, cy={result['cy']:.2f}"

    def test_analytics_from_dict_roundtrip(self):
        """ImageAnalytics.from_dict() → .to_dict() == исходный dict."""
        from retouch.processing.analysis import ImageAnalytics

        original = {
            'median_brightness': 130.0,
            'mean_brightness': 125.0,
            'p10_brightness': 45.0,
            'p25_brightness': 80.0,
            'p75_brightness': 180.0,
            'p90_brightness': 210.0,
            'tonal_range': 165.0,
            'highlight_clipping_pct': 0.5,
            'shadow_clipping_pct': 2.0,
            'bg_median_brightness': 10.0,
            'bg_mean_brightness': 12.0,
            'subject_separation': 120.0,
            'input_class': 'medium',
        }

        result = ImageAnalytics.from_dict(original).to_dict()
        assert result == original

    def test_wide_image_preview_height(self, tmp_path):
        """Широкий кадр 4000x500 → height >= 200."""
        from retouch.processing.pipeline import process_preview

        # Широкое изображение
        arr = np.zeros((500, 4000, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        # Субъект
        y, x = np.ogrid[:500, :4000]
        ellipse = ((x - 2000) / 200) ** 2 + ((y - 250) / 100) ** 2 <= 1.0
        arr[ellipse, 0] = 180
        arr[ellipse, 1] = 140
        arr[ellipse, 2] = 120
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr, "RGBA")
        input_path = str(tmp_path / "wide.png")
        img.save(input_path, "PNG")

        # Отключаем валидацию разрешения — широкий кадр легален
        import copy
        config = copy.deepcopy(DEFAULTS)
        config["processing"]["min_resolution"] = 0
        config["processing"]["min_blue_ratio"] = 0.0

        result = process_preview(input_path, machine_type="laser_standard",
                                  config=config, max_size=768)

        # Высота должна быть >= 200 (D.2)
        assert result.height >= 200, f"Высота {result.height} < 200"


class TestG3Integration:
    """G.3: Интеграционный тест — сквозной пайплайн."""

    def test_full_pipeline_laser(self, tmp_path):
        """Сквозной: загрузка → детекция → preview → export → BMP валидация."""
        from retouch.processing.pipeline import process_export

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 150
        arr[ellipse, 1] = 120
        arr[ellipse, 2] = 100
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr, "RGBA")
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        output_bmp = str(tmp_path / "output.bmp")

        result = process_export(
            input_path, output_bmp,
            machine_type="laser_standard", config=DEFAULTS,
        )

        # BMP создан и валиден
        assert os.path.isfile(output_bmp)
        with Image.open(output_bmp) as bmp:
            assert bmp.mode in ("L", "P", "RGB")

        # PNG создан
        assert os.path.isfile(str(tmp_path / "output.png"))

        # Промежуточные освобождены
        assert result.img_chromakey is None
        assert result.img_final is not None

        # Диагностика собрана
        assert result.glow_size > 0
        assert result.face_brightness_before >= 0

    def test_full_pipeline_impact(self, tmp_path):
        """Сквозной impact: shadow_floor + shadow_noise + white_ceiling."""
        from retouch.processing.pipeline import process_export

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 80
        arr[ellipse, 1] = 60
        arr[ellipse, 2] = 40
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr, "RGBA")
        input_path = str(tmp_path / "dark.png")
        img.save(input_path, "PNG")

        output_bmp = str(tmp_path / "output.bmp")

        result = process_export(
            input_path, output_bmp,
            machine_type="impact", config=DEFAULTS,
        )

        assert os.path.isfile(output_bmp)
        assert result.img_final is not None

    def test_face_oval_override(self, tmp_path):
        """Ручной овал (face_oval) интегрируется в пайплайн."""
        from retouch.processing.pipeline import process_steps

        arr = np.zeros((512, 512, 4), dtype=np.uint8)
        arr[..., 2] = 255
        arr[..., 3] = 255
        y, x = np.ogrid[:512, :512]
        ellipse = ((x - 256) / 100) ** 2 + ((y - 256) / 120) ** 2 <= 1.0
        arr[ellipse, 0] = 150
        arr[ellipse, 1] = 120
        arr[ellipse, 2] = 100
        arr[ellipse, 3] = 255

        img = Image.fromarray(arr, "RGBA")
        input_path = str(tmp_path / "input.png")
        img.save(input_path, "PNG")

        # Ручной овал
        manual_oval = {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20, "source": "manual"}

        result = process_steps(
            input_path, machine_type="laser_standard",
            config=DEFAULTS, face_oval=manual_oval,
        )

        # face_mask создан из ручного овала
        assert result.face_mask is not None
