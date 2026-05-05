"""Tests for the config router — with file-system isolation."""

import pytest
from pathlib import Path

from retouch_ui.backend.routers import config as config_router_module


def test_get_config(client):
    """GET /api/config returns config + warnings."""
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "config" in data
    assert "warnings" in data
    assert isinstance(data["warnings"], list)


def test_get_defaults(client):
    """GET /api/config/defaults returns defaults with processing."""
    res = client.get("/api/config/defaults")
    assert res.status_code == 200
    data = res.json()
    assert "defaults" in data
    assert "processing" in data["defaults"]
    assert "laser" in data["defaults"]["processing"]
    assert "vignette" in data["defaults"]


def test_put_config_uses_tmp(tmp_path, monkeypatch):
    """PUT /api/config saves to temp file (isolation via monkeypatch)."""
    tmp_config = tmp_path / "config.yaml"
    _fake_path = lambda: tmp_config

    # Patch both the source module AND the router's local reference
    from retouch import config as cfg_module
    monkeypatch.setattr(cfg_module, "find_config_path", _fake_path)
    monkeypatch.setattr(config_router_module, "find_config_path", _fake_path)

    from fastapi.testclient import TestClient
    from retouch_ui.backend.main import app
    client = TestClient(app)

    # Get current config
    current = client.get("/api/config").json()

    # Save (unchanged) to tmp_path
    res = client.put(
        "/api/config",
        json={"config": current["config"]},
    )
    assert res.status_code == 200
    assert res.json()["saved"] is True
    assert tmp_config.exists()


def test_put_config_deep_merge(tmp_path, monkeypatch):
    """PUT /api/config with partial config — deep_merge fills missing keys (A3)."""
    tmp_config = tmp_path / "config.yaml"
    _fake_path = lambda: tmp_config

    from retouch import config as cfg_module
    monkeypatch.setattr(cfg_module, "find_config_path", _fake_path)
    monkeypatch.setattr(config_router_module, "find_config_path", _fake_path)

    from fastapi.testclient import TestClient
    from retouch_ui.backend.main import app
    client = TestClient(app)

    # Send partial config (only brightness override)
    partial = {"processing": {"laser": {"brightness": 1.30}}}
    res = client.put(
        "/api/config",
        json={"config": partial},
    )
    assert res.status_code == 200

    # Verify saved config has ALL keys (deep_merge with DEFAULTS)
    import yaml
    saved = yaml.safe_load(tmp_config.read_text())
    assert saved["processing"]["laser"]["brightness"] == 1.30
    assert "glow_size_min" in saved["processing"]["laser"]  # from DEFAULTS
    assert "vignette" in saved  # from DEFAULTS


def test_put_config_returns_warnings(tmp_path, monkeypatch):
    """PUT /api/config with bad config returns warnings but still saves."""
    tmp_config = tmp_path / "config.yaml"
    _fake_path = lambda: tmp_config

    from retouch import config as cfg_module
    monkeypatch.setattr(cfg_module, "find_config_path", _fake_path)
    monkeypatch.setattr(config_router_module, "find_config_path", _fake_path)

    from fastapi.testclient import TestClient
    from retouch_ui.backend.main import app
    client = TestClient(app)

    # Send inverted range config
    bad = {"processing": {"laser": {"glow_size_min": 100, "glow_size_max": 10}}}
    res = client.put(
        "/api/config",
        json={"config": bad},
    )
    assert res.status_code == 200
    assert len(res.json()["warnings"]) > 0
    # File saved in isolated directory, not project root
    assert tmp_config.exists()
