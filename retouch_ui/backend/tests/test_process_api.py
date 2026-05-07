"""Tests for the process router: upload, preview, export."""

import io
import json

import pytest
from PIL import Image

from retouch_ui.backend.routers.process import _uploaded_files, MAX_UPLOADED_FILES


# ─── Upload ───────────────────────────────────────────────────────────────


def test_upload_returns_file_id(client, sample_chromakey_png):
    """POST /api/upload returns file_id."""
    res = client.post(
        "/api/upload",
        files={"file": ("test.png", sample_chromakey_png, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "file_id" in data
    assert len(data["file_id"]) > 0
    assert data["filename"] == "test.png"
    assert data["size_bytes"] > 0


def test_upload_invalid_file_type(client):
    """Uploading a non-image returns 400."""
    res = client.post(
        "/api/upload",
        files={"file": ("test.txt", b"not an image", "text/plain")},
    )
    assert res.status_code == 400


def test_upload_jpeg_accepted(client):
    """JPEG files are accepted."""
    img = Image.new("RGB", (64, 64), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    res = client.post(
        "/api/upload",
        files={"file": ("photo.jpg", buf, "image/jpeg")},
    )
    assert res.status_code == 200


def test_upload_tiff_accepted(client):
    """TIFF files are accepted."""
    img = Image.new("RGB", (64, 64), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="TIFF")
    buf.seek(0)
    res = client.post(
        "/api/upload",
        files={"file": ("photo.tiff", buf, "image/tiff")},
    )
    assert res.status_code == 200


def test_upload_limit(client, monkeypatch):
    """Uploading beyond MAX_UPLOADED_FILES returns 503."""
    # Fill the store to capacity
    _uploaded_files.clear()
    for i in range(MAX_UPLOADED_FILES):
        _uploaded_files[f"fake-{i}"] = (None, f"file-{i}.png")

    try:
        img = Image.new("RGB", (64, 64), (0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        res = client.post(
            "/api/upload",
            files={"file": ("extra.png", buf, "image/png")},
        )
        assert res.status_code == 503
    finally:
        _uploaded_files.clear()


# ─── Preview ──────────────────────────────────────────────────────────────


def test_preview_by_file_id(client, uploaded_file_id):
    """POST /api/process/preview returns JSON with images + diagnostics."""
    res = client.post(
        "/api/process/preview",
        json={"file_id": uploaded_file_id, "machine": "laser_standard"},
    )
    assert res.status_code == 200
    data = res.json()
    # Проверяем структуру ответа
    assert "images" in data
    assert "diagnostics" in data
    assert "warnings" in data
    # Должен быть минимум шаг "final"
    assert "final" in data["images"]
    assert data["images"]["final"].startswith("data:image/png;base64,")
    # Диагностика
    diag = data["diagnostics"]
    assert "glow_size" in diag
    assert "face_brightness_before" in diag
    assert "face_brightness_after" in diag


def test_preview_with_custom_params(client, uploaded_file_id):
    """Preview with params override works."""
    res = client.post(
        "/api/process/preview",
        json={
            "file_id": uploaded_file_id,
            "machine": "laser_standard",
            "params": {"processing": {"laser_standard": {"brightness": 1.40}}},
        },
    )
    assert res.status_code == 200


def test_preview_laser_standard_vs_impact(client, uploaded_file_id):
    """Laser standard and impact give different glow_size."""
    results = {}
    for machine in ("laser_standard", "impact"):
        res = client.post(
            "/api/process/preview",
            json={"file_id": uploaded_file_id, "machine": machine},
        )
        assert res.status_code == 200
        data = res.json()
        results[machine] = data["diagnostics"]["glow_size"]

    assert results["laser_standard"] != results["impact"]


def test_preview_laser_80w(client, uploaded_file_id):
    """POST /api/process/preview with laser_80w returns valid result."""
    res = client.post(
        "/api/process/preview",
        json={"file_id": uploaded_file_id, "machine": "laser_80w"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "final" in data["images"]
    assert data["images"]["final"].startswith("data:image/png;base64,")


def test_preview_invalid_file_id(client):
    """Nonexistent file_id returns 404."""
    res = client.post(
        "/api/process/preview",
        json={"file_id": "nonexistent-id-12345", "machine": "laser_standard"},
    )
    assert res.status_code == 404


# ─── Export ────────────────────────────────────────────────────────────────


def test_export_returns_png(client, uploaded_file_id):
    """POST /api/process/export with format=png returns PNG."""
    res = client.post(
        "/api/process/export",
        json={"file_id": uploaded_file_id, "machine": "laser_standard", "format": "png"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 0


def test_export_returns_tiff(client, uploaded_file_id):
    """POST /api/process/export with format=tiff returns TIFF."""
    res = client.post(
        "/api/process/export",
        json={"file_id": uploaded_file_id, "machine": "laser_standard", "format": "tiff"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/tiff"
    assert len(res.content) > 0


def test_export_invalid_file_id(client):
    """Nonexistent file_id returns 404."""
    res = client.post(
        "/api/process/export",
        json={"file_id": "nonexistent-id-12345", "machine": "laser_standard"},
    )
    assert res.status_code == 404


def test_export_with_params(client, uploaded_file_id):
    """Export with params override works."""
    res = client.post(
        "/api/process/export",
        json={
            "file_id": uploaded_file_id,
            "machine": "laser_standard",
            "format": "png",
            "params": {"processing": {"laser_standard": {"brightness": 1.30}}},
        },
    )
    assert res.status_code == 200


# ─── Vignette Mask ─────────────────────────────────────────────────────────


def test_vignette_mask_endpoint(client):
    """POST /api/vignette/mask returns base64 PNG mask + params."""
    res = client.post(
        "/api/vignette/mask",
        json={
            "width": 512,
            "height": 512,
            "vignette": {
                "vertical_offset": 0.1,
                "vertical_diameter": 0.5,
                "blur_radius": 60,
                "headroom": 0.6,
                "horizontal_oversize": 0.2,
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "mask" in data
    assert data["mask"].startswith("data:image/png;base64,")
    assert "params" in data
    assert "arch_top_y" in data["params"]
    assert "arch_bottom_y" in data["params"]
    assert "h_oversize" in data["params"]
    # Проверяем вычисленные параметры
    assert data["params"]["arch_bottom_y"] == pytest.approx(512 - 512 * 0.1, abs=1)
    assert data["params"]["h_oversize"] == pytest.approx(512 * 0.2, abs=1)


def test_vignette_mask_invalid_params(client):
    """POST /api/vignette/mask with invalid width returns 422."""
    res = client.post(
        "/api/vignette/mask",
        json={
            "width": 10,  # < 64
            "height": 512,
            "vignette": {},
        },
    )
    assert res.status_code == 422


def test_vignette_mask_different_sizes(client):
    """POST /api/vignette/mask works for various image sizes."""
    for w, h in [(256, 256), (512, 768), (1024, 768)]:
        res = client.post(
            "/api/vignette/mask",
            json={
                "width": w,
                "height": h,
                "vignette": {
                    "vertical_offset": 0.1,
                    "vertical_diameter": 0.5,
                    "blur_radius": 30,
                    "headroom": 0.6,
                    "horizontal_oversize": 0.2,
                },
            },
        )
        assert res.status_code == 200
        assert res.json()["mask"].startswith("data:image/png;base64,")
