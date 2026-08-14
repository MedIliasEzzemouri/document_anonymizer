def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}".format(tmp_path / "api.db"))
    from fastapi.testclient import TestClient
    from anonymizer.api import app
    return TestClient(app)


def test_health(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
