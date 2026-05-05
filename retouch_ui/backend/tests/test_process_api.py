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
    """POST /api/process/preview returns PNG image with diagnostics headers."""
    res = client.post(
        "/api/process/preview",
        json={"file_id": uploaded_file_id, "machine": "laser"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 0
    # Check diagnostic headers
    assert "X-Diagnostics-Glow-Size" in res.headers
    assert "X-Diagnostics-Face-Brightness-Before" in res.headers
    assert "X-Diagnostics-Face-Brightness-After" in res.headers


def test_preview_with_custom_params(client, uploaded_file_id):
    """Preview with params override works."""
    res = client.post(
        "/api/process/preview",
        json={
            "file_id": uploaded_file_id,
            "machine": "laser",
            "params": {"processing": {"laser": {"brightness": 1.40}}},
        },
    )
    assert res.status_code == 200


def test_preview_laser_vs_impact(client, uploaded_file_id):
    """Laser and impact give different glow_size."""
    results = {}
    for machine in ("laser", "impact"):
        res = client.post(
            "/api/process/preview",
            json={"file_id": uploaded_file_id, "machine": machine},
        )
        assert res.status_code == 200
        results[machine] = res.headers.get("X-Diagnostics-Glow-Size", "0")

    assert results["laser"] != results["impact"]


def test_preview_invalid_file_id(client):
    """Nonexistent file_id returns 404."""
    res = client.post(
        "/api/process/preview",
        json={"file_id": "nonexistent-id-12345", "machine": "laser"},
    )
    assert res.status_code == 404


# ─── Export ────────────────────────────────────────────────────────────────


def test_export_returns_png(client, uploaded_file_id):
    """POST /api/process/export with format=png returns PNG."""
    res = client.post(
        "/api/process/export",
        json={"file_id": uploaded_file_id, "machine": "laser", "format": "png"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 0


def test_export_returns_tiff(client, uploaded_file_id):
    """POST /api/process/export with format=tiff returns TIFF."""
    res = client.post(
        "/api/process/export",
        json={"file_id": uploaded_file_id, "machine": "laser", "format": "tiff"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/tiff"
    assert len(res.content) > 0


def test_export_invalid_file_id(client):
    """Nonexistent file_id returns 404."""
    res = client.post(
        "/api/process/export",
        json={"file_id": "nonexistent-id-12345", "machine": "laser"},
    )
    assert res.status_code == 404


def test_export_with_params(client, uploaded_file_id):
    """Export with params override works."""
    res = client.post(
        "/api/process/export",
        json={
            "file_id": uploaded_file_id,
            "machine": "laser",
            "format": "png",
            "params": {"processing": {"laser": {"brightness": 1.30}}},
        },
    )
    assert res.status_code == 200
