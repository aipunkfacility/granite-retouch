"""Tests for GET /api/health endpoint."""


def test_health_returns_ok(client):
    """GET /api/health returns status=ok and version."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert len(data["version"]) > 0


def test_health_version_matches_package(client):
    """Health endpoint version matches retouch.__version__."""
    from retouch import __version__
    res = client.get("/api/health")
    assert res.json()["version"] == __version__
