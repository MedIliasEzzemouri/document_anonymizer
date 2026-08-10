from anonymizer.pipeline import anonymize_text
from anonymizer.detectors.ner_detector import NerDetector
from anonymizer.detectors.regex_rules import RegexDetector
from anonymizer.entities import EntityType


def fake_engine(spans):
    def run(text):
        return list(spans)
    return run


def test_regex_and_ner_merge_and_redact():
    text = "Ahmed emailed a@b.com"
    ner = NerDetector({"eng": fake_engine([("PERSON", 0, 5)])})
    result = anonymize_text(text, detectors=[RegexDetector(), ner])
    assert "[PERSON]" in result.redacted_text
    assert "[EMAIL]" in result.redacted_text
    assert "Ahmed" not in result.redacted_text
    assert "a@b.com" not in result.redacted_text


def test_types_filter_applies_to_ner_too():
    text = "Ahmed emailed a@b.com"
    ner = NerDetector({"eng": fake_engine([("PERSON", 0, 5)])})
    result = anonymize_text(text, types=[EntityType.EMAIL], detectors=[RegexDetector(), ner])
    assert "Ahmed" in result.redacted_text        # PERSON filtered out
    assert "a@b.com" not in result.redacted_text   # EMAIL kept


def test_build_detectors_regex_only_by_default():
    from anonymizer.pipeline import build_detectors
    ds = build_detectors()
    assert len(ds) == 1
    assert isinstance(ds[0], RegexDetector)
