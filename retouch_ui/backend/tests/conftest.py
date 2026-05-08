"""Shared fixtures for backend API tests."""

import io
from pathlib import Path

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from ..main import app


@pytest.fixture
def client():
    """FastAPI TestClient (synchronous — no async def needed)."""
    return TestClient(app)


@pytest.fixture
def sample_chromakey_png():
    """Synthetic blue-background PNG as BytesIO — for upload tests."""
    import numpy as np

    arr = np.zeros((512, 512, 4), dtype=np.uint8)
    arr[:, :] = [0, 0, 255, 255]           # blue background (RGBA)
    arr[200:312, 200:312] = [180, 140, 120, 255]  # skin-colored subject

    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@pytest.fixture
def uploaded_file_id(client, sample_chromakey_png):
    """Upload a file via POST /api/upload — returns file_id."""
    res = client.post(
        "/api/upload",
        files={"file": ("test.png", sample_chromakey_png, "image/png")},
    )
    assert res.status_code == 200, f"Upload failed: {res.text}"
    return res.json()["file_id"]
