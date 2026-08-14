import pytest

pytest.importorskip("sqlalchemy")


def test_record_and_list_job(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}".format(tmp_path / "t.db"))
    from anonymizer import db

    db.init_db()
    jid = db.record_job("cv.pdf", "secure", True, {"EMAIL": 2, "PERSON": 1})
    assert isinstance(jid, int)

    jobs = db.list_jobs()
    assert jobs[0]["filename"] == "cv.pdf"
    assert jobs[0]["mode"] == "secure"
    assert jobs[0]["ner"] is True
    assert jobs[0]["counts"] == {"EMAIL": 2, "PERSON": 1}
    assert jobs[0]["total_entities"] == 3
    assert isinstance(jobs[0]["created_at"], str)  # JSON-serializable


def test_list_jobs_newest_first(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}".format(tmp_path / "t2.db"))
    from anonymizer import db

    db.init_db()
    db.record_job("a.pdf", "secure", False, {"EMAIL": 1})
    db.record_job("b.pdf", "secure", False, {"PHONE": 1})
    jobs = db.list_jobs()
    assert jobs[0]["filename"] == "b.pdf"  # newest first
