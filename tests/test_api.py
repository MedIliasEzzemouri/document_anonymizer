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


import json
import pytest

fitz = pytest.importorskip("fitz")


def _pdf(body):
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), body, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.mark.slow
def test_redact_returns_clean_pdf_and_records_job(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        files = {"file": ("cv.pdf", _pdf("Email a@b.com here"), "application/pdf")}
        r = client.post("/redact", files=files, data={"mode": "secure"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        reopened = fitz.open(stream=r.content, filetype="pdf")
        text = "".join(p.get_text() for p in reopened)
        reopened.close()
        assert "a@b.com" not in text
        counts = json.loads(r.headers["x-redaction-counts"])
        assert counts.get("EMAIL", 0) >= 1

        audit = client.get("/audit").json()
        assert audit[0]["filename"] == "cv.pdf"
        assert audit[0]["total_entities"] >= 1


def test_redact_rejects_non_pdf(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        files = {"file": ("note.txt", b"hello", "text/plain")}
        r = client.post("/redact", files=files, data={"mode": "secure"})
        assert r.status_code == 400


def test_audit_empty(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        assert client.get("/audit").json() == []


def test_root_serves_html(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
