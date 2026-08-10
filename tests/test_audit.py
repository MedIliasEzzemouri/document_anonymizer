import hashlib
import json

from anonymizer.audit import build_audit_log
from anonymizer.entities import Entity, EntityType, Span


def sample_entities():
    e1 = Entity(EntityType.EMAIL, "a@b.com", Span(0, 7), "regex")
    e1.replacement = "[EMAIL_1]"
    e2 = Entity(EntityType.EMAIL, "a@b.com", Span(12, 19), "regex")
    e2.replacement = "[EMAIL_1]"
    return [e1, e2]


def test_audit_shape_and_counts():
    log = build_audit_log("f.txt", "consistent", sample_entities())
    assert log["source"] == "f.txt"
    assert log["style"] == "consistent"
    assert log["counts"] == {"EMAIL": 2}
    assert log["entities"][0]["original"] == "a@b.com"
    assert log["entities"][0]["replacement"] == "[EMAIL_1]"
    assert log["entities"][0]["start"] == 0
    # must be JSON-serializable
    json.dumps(log)


def test_redact_audit_hashes_original():
    log = build_audit_log("f.txt", "labeled", sample_entities(), redact_audit=True)
    expected = hashlib.sha256("a@b.com".encode("utf-8")).hexdigest()
    assert log["entities"][0]["original"] == expected
    assert "a@b.com" not in json.dumps(log)
