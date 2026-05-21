"""Общие фикстуры для тестов granite-retouch.

Создаёт синтетические PNG-изображения с синим хромакеем
для воспроизводимого тестирования без реальных фото.
"""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Синтетические изображения
# ---------------------------------------------------------------------------

def make_chromakey_image(width=512, height=512,
                         subject_color=(180, 140, 120),
                         bg_color=(0, 0, 255)):
    """Создать синтетическое RGBA-изображение с синим хромакеем.

    Центральный эллипс — «субъект», остальное — синий фон #0000FF.

    Returns:
        tuple: (PIL.Image RGBA, subject_mask L)
    """
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    mask = np.zeros((height, width), dtype=np.uint8)

    # Синий фон
    arr[..., 0] = bg_color[0]
    arr[..., 1] = bg_color[1]
    arr[..., 2] = bg_color[2]
    arr[..., 3] = 255

    # Эллипс-субъект в центре (60% ширины, 70% высоты)
    cx, cy = width // 2, height // 2
    rx, ry = int(width * 0.30), int(height * 0.35)

    y_coords, x_coords = np.ogrid[:height, :width]
    ellipse = ((x_coords - cx) / rx) ** 2 + ((y_coords - cy) / ry) ** 2 <= 1.0

    arr[ellipse, 0] = subject_color[0]
    arr[ellipse, 1] = subject_color[1]
    arr[ellipse, 2] = subject_color[2]
    arr[ellipse, 3] = 255
    mask[ellipse] = 255

    img = Image.fromarray(arr)
    subject_mask = Image.fromarray(mask)
    return img, subject_mask


def make_portrait_image(width=512, height=512):
    """Создать синтетический «портрет» — эллипс-голова + плечи.

    Имитирует структуру реального портрета:
    - Голова (верхний эллипс) — лицо
    - Плечи (нижний широкий эллипс) — одежда
    - Синий фон

    Returns:
        tuple: (PIL.Image RGBA, subject_mask L)
    """
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    mask = np.zeros((height, width), dtype=np.uint8)

    # Синий фон
    arr[..., 2] = 255
    arr[..., 3] = 255

    y_coords, x_coords = np.ogrid[:height, :width]

    # Голова — верхний эллипс
    cx, cy_head = width // 2, int(height * 0.30)
    rx_head, ry_head = int(width * 0.18), int(height * 0.15)
    head = ((x_coords - cx) / rx_head) ** 2 + ((y_coords - cy_head) / ry_head) ** 2 <= 1.0

    # Плечи — нижний широкий эллипс
    cy_shoulders = int(height * 0.65)
    rx_shoulders, ry_shoulders = int(width * 0.35), int(height * 0.25)
    shoulders = ((x_coords - cx) / rx_shoulders) ** 2 + ((y_coords - cy_shoulders) / ry_shoulders) ** 2 <= 1.0

    # Соединяем голову и плечи (шея)
    neck_width = int(width * 0.08)
    neck_top = cy_head + ry_head
    neck_bottom = cy_shoulders - ry_shoulders // 2
    neck = ((x_coords >= cx - neck_width) & (x_coords <= cx + neck_width) &
            (y_coords >= neck_top) & (y_coords <= neck_bottom))

    # Субъект = голова + шея + плечи
    subject = head | neck | shoulders
    arr[subject, 0] = 180
    arr[subject, 1] = 140
    arr[subject, 2] = 120
    arr[subject, 3] = 255
    mask[subject] = 255

    img = Image.fromarray(arr)
    subject_mask = Image.fromarray(mask)
    return img, subject_mask


def make_no_chromakey_image(width=512, height=512):
    """Изображение БЕЗ синего хромакея — для негативных тестов."""
    arr = np.full((height, width, 4), [120, 100, 80, 255], dtype=np.uint8)
    return Image.fromarray(arr)


def make_small_image(width=100, height=100):
    """Маленькое изображение с хромакеем (ниже min_resolution)."""
    return make_chromakey_image(width, height)


def make_dark_blue_clothing_image(width=512, height=512):
    """Изображение с тёмно-синей «одеждой» — не должна удаляться как хромакей.

    Верхняя треть — субъект (кожа), нижняя треть — тёмно-синяя одежда (B=80),
    остальное — хромакей #0000FF.
    """
    arr = np.zeros((height, width, 4), dtype=np.uint8)

    # Синий хромакей
    arr[..., 0] = 0
    arr[..., 1] = 0
    arr[..., 2] = 255
    arr[..., 3] = 255

    # Субъект — верхняя треть (кожа)
    arr[:height // 3, :, 0] = 180
    arr[:height // 3, :, 1] = 140
    arr[:height // 3, :, 2] = 120

    # Тёмно-синяя одежда — нижняя треть
    arr[2 * height // 3:, :, 0] = 30
    arr[2 * height // 3:, :, 1] = 40
    arr[2 * height // 3:, :, 2] = 80

    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# Фикстуры pytest
# ---------------------------------------------------------------------------

@pytest.fixture
def chromakey_img():
    """Синтетическое изображение с синим хромакеем."""
    img, mask = make_chromakey_image()
    return img, mask


@pytest.fixture
def portrait_img():
    """Синтетический «портрет» — голова + плечи."""
    return make_portrait_image()


@pytest.fixture
def no_chromakey_img():
    """Изображение без синего хромакея."""
    return make_no_chromakey_image()


@pytest.fixture
def small_chromakey_img():
    """Маленькое изображение с хромакеем (100x100)."""
    return make_chromakey_image(100, 100)


@pytest.fixture
def dark_blue_clothing_img():
    """Изображение с тёмно-синей одеждой."""
    return make_dark_blue_clothing_image()


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Временная директория для выходных файлов."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def chromakey_png(tmp_path, chromakey_img):
    """Сохранить chromakey-изображение как PNG и вернуть путь."""
    img, _ = chromakey_img
    p = tmp_path / "test_input.png"
    img.save(str(p), "PNG")
    return str(p)


@pytest.fixture
def portrait_png(tmp_path, portrait_img):
    """Сохранить портрет как PNG и вернуть путь."""
    img, _ = portrait_img
    p = tmp_path / "portrait_input.png"
    img.save(str(p), "PNG")
    return str(p)


@pytest.fixture
def small_chromakey_png(tmp_path, small_chromakey_img):
    """Маленький PNG (100x100) для тестов валидации разрешения."""
    img, _ = small_chromakey_img
    p = tmp_path / "small_input.png"
    img.save(str(p), "PNG")
    return str(p)


@pytest.fixture
def no_chromakey_png(tmp_path, no_chromakey_img):
    """PNG без хромакея для негативных тестов."""
    img = no_chromakey_img
    p = tmp_path / "no_chroma.png"
    img.save(str(p), "PNG")
    return str(p)


@pytest.fixture
def default_config():
    """Конфигурация DEFAULTS из retouch.config."""
    from retouch.config import DEFAULTS
    return DEFAULTS


@pytest.fixture
def laser_config(default_config):
    """Конфигурация с laser_standard-параметрами."""
    return default_config


@pytest.fixture
def impact_config(default_config):
    """Конфигурация с impact-параметрами."""
    return default_config


@pytest.fixture
def schema_path():
    """Путь к orders/schema.json."""
    return str(Path(__file__).resolve().parent.parent / "orders" / "schema.json")


@pytest.fixture
def valid_order_json(tmp_path, schema_path):
    """Создать валидный order.json и вернуть путь."""
    order = {
        "order_id": "ORD-2026-042",
        "machine_type": "laser_standard",
        "source_photo": "source.jpg",
        "status": "new",
    }
    p = tmp_path / "order.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(order, f, indent=2, ensure_ascii=False)
    return str(p)


@pytest.fixture
def invalid_order_json(tmp_path):
    """Создать невалидный order.json (нет обязательных полей)."""
    order = {
        "order_id": "BAD-ID",
        # Нет machine_type, source_photo, status
    }
    p = tmp_path / "bad_order.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(order, f, indent=2, ensure_ascii=False)
    return str(p)


@pytest.fixture
def order_with_crm(tmp_path, schema_path):
    """Заказ с привязкой к CRM."""
    order = {
        "order_id": "ORD-2026-007",
        "crm_company_id": "CMP-0042",
        "machine_type": "impact",
        "source_photo": "source.jpg",
        "status": "done",
    }
    p = tmp_path / "order_crm.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(order, f, indent=2, ensure_ascii=False)
    return str(p)


# ---------------------------------------------------------------------------
# Новые фикстуры (C.4)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_face_oval():
    """Типичный овал лица для тестов."""
    return {"cx": 0.5, "cy": 0.25, "rx": 0.15, "ry": 0.20, "source": "auto"}


@pytest.fixture
def img_gray_512():
    """Grayscale-изображение 512x512 с эллипсом-субъектом."""
    arr = np.full((512, 512), 40, dtype=np.uint8)
    y, x = np.ogrid[:512, :512]
    ellipse = ((x - 256) / 150) ** 2 + ((y - 256) / 175) ** 2 <= 1.0
    arr[ellipse] = 140
    return Image.fromarray(arr)


@pytest.fixture
def subject_mask_512():
    """Маска субъекта 512x512 — эллипс."""
    mask = np.zeros((512, 512), dtype=np.uint8)
    y, x = np.ogrid[:512, :512]
    ellipse = ((x - 256) / 150) ** 2 + ((y - 256) / 175) ** 2 <= 1.0
    mask[ellipse] = 255
    return Image.fromarray(mask)


@pytest.fixture
def sample_pipeline_context(img_gray_512, subject_mask_512):
    """C.4: Типичный PipelineContext для тестов."""
    from retouch.processing.core.context import PipelineContext
    return PipelineContext(
        img_gray=img_gray_512,
        subject_mask=subject_mask_512,
        machine_type="impact",
    )


@pytest.fixture
def sample_analytics():
    """Типичные метрики аналитики."""
    from retouch.processing.analysis.analysis import ImageAnalytics
    return ImageAnalytics(
        median_brightness=130.0, mean_brightness=125.0,
        p10_brightness=45.0, p25_brightness=80.0,
        p75_brightness=180.0, p90_brightness=210.0,
        tonal_range=165.0,
        highlight_clipping_pct=0.5, shadow_clipping_pct=2.0,
        bg_median_brightness=10.0, bg_mean_brightness=12.0,
        subject_separation=120.0,
        input_class="medium",
    )
