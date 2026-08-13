from anonymizer.pipeline import detect_entities
from anonymizer.detectors.ner_detector import NerDetector
from anonymizer.entities import EntityType


def fake_engine(spans):
    def run(text):
        return list(spans)
    return run


def test_detect_entities_finds_regex_pii():
    ents = detect_entities("mail a@b.com")
    assert any(e.type == EntityType.EMAIL for e in ents)


def test_detect_entities_excludes_org_by_default():
    ner = NerDetector({"e": fake_engine([("ORG", 0, 4)])})
    ents = detect_entities("ACME hires", detectors=[ner])
    assert all(e.type != EntityType.ORG for e in ents)


def test_detect_entities_resolves_overlaps():
    # regex should not emit the same email span twice
    ents = detect_entities("mail a@b.com")
    emails = [e for e in ents if e.type == EntityType.EMAIL]
    assert len(emails) == 1
