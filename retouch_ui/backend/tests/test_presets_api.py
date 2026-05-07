"""Tests for the presets router — with directory isolation."""

import pytest
from pathlib import Path


def test_list_presets(client):
    """GET /api/presets returns list."""
    res = client.get("/api/presets")
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert isinstance(data["presets"], list)


def test_list_presets_with_isolation(client, tmp_path, monkeypatch):
    """GET /api/presets with isolated empty dir returns empty list."""
    from retouch_ui.backend.routers import presets as presets_module
    monkeypatch.setattr(presets_module, "_presets_dir", lambda: tmp_path)

    res = client.get("/api/presets")
    assert res.status_code == 200
    assert res.json()["presets"] == []


def test_create_and_delete_preset(client, tmp_path, monkeypatch):
    """Create and delete a preset in isolated directory."""
    from retouch_ui.backend.routers import presets as presets_module
    monkeypatch.setattr(presets_module, "_presets_dir", lambda: tmp_path)

    # Create
    res = client.post(
        "/api/presets",
        json={
            "name": "test-isolated",
            "config": {"processing": {"laser_standard": {"brightness": 1.20}}},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "test-isolated"

    # Verify file exists
    assert (tmp_path / "test-isolated.yaml").exists()

    # Delete
    res = client.delete("/api/presets/test-isolated")
    assert res.status_code == 200
    assert res.json()["deleted"] == "test-isolated"

    # Verify file removed
    assert not (tmp_path / "test-isolated.yaml").exists()


def test_create_duplicate_preset(client, tmp_path, monkeypatch):
    """Cannot create preset with existing name — returns 409."""
    from retouch_ui.backend.routers import presets as presets_module
    monkeypatch.setattr(presets_module, "_presets_dir", lambda: tmp_path)

    # First creation
    res = client.post("/api/presets", json={"name": "dup-test", "config": {}})
    assert res.status_code == 200

    # Duplicate creation
    res = client.post("/api/presets", json={"name": "dup-test", "config": {}})
    assert res.status_code == 409

    # Cleanup
    client.delete("/api/presets/dup-test")


def test_delete_nonexistent_preset(client, tmp_path, monkeypatch):
    """Deleting a nonexistent preset returns 404."""
    from retouch_ui.backend.routers import presets as presets_module
    monkeypatch.setattr(presets_module, "_presets_dir", lambda: tmp_path)

    res = client.delete("/api/presets/does-not-exist")
    assert res.status_code == 404


def test_create_preset_with_unsafe_name(client, tmp_path, monkeypatch):
    """Preset name with path traversal chars is rejected or sanitized."""
    from retouch_ui.backend.routers import presets as presets_module
    monkeypatch.setattr(presets_module, "_presets_dir", lambda: tmp_path)

    res = client.post("/api/presets", json={"name": "../etc/passwd", "config": {}})
    # Either 400 (rejected) or sanitized
    if res.status_code == 200:
        # Name should be sanitized
        assert res.json()["name"] != "../etc/passwd"
    else:
        assert res.status_code == 400


def test_preset_roundtrip(client, tmp_path, monkeypatch):
    """Preset config round-trips correctly through create → list."""
    from retouch_ui.backend.routers import presets as presets_module
    monkeypatch.setattr(presets_module, "_presets_dir", lambda: tmp_path)

    config_data = {"processing": {"laser_standard": {"brightness": 1.25}}}
    res = client.post(
        "/api/presets",
        json={"name": "roundtrip", "config": config_data},
    )
    assert res.status_code == 200

    # List and find
    res = client.get("/api/presets")
    presets = res.json()["presets"]
    found = [p for p in presets if p["name"] == "roundtrip"]
    assert len(found) == 1
    assert found[0]["config"]["processing"]["laser_standard"]["brightness"] == 1.25

    # Cleanup
    client.delete("/api/presets/roundtrip")
