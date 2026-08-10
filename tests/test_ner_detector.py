from anonymizer.detectors.ner_detector import NerDetector, LABEL_MAP
from anonymizer.entities import EntityType


def fake_engine(spans):
    # spans: list of (label, start, end); returns an engine ignoring its input
    def run(text):
        return list(spans)
    return run


def test_maps_labels_and_sets_span_and_provenance():
    text = "Call Ahmed Benali now"
    engines = {"spacy-en": fake_engine([("PERSON", 5, 17)])}
    ents = NerDetector(engines).detect(text)
    assert len(ents) == 1
    e = ents[0]
    assert e.type == EntityType.PERSON
    assert e.detector == "spacy-en"
    assert text[e.span.start:e.span.end] == "Ahmed Benali"
    assert e.text == "Ahmed Benali"


def test_label_aliases_normalize():
    text = "Paris and ACME"
    engines = {"eng": fake_engine([("GPE", 0, 5), ("PER", 10, 14)])}
    types = {e.type for e in NerDetector(engines).detect(text)}
    assert EntityType.LOC in types      # GPE -> LOC
    assert EntityType.PERSON in types   # PER -> PERSON


def test_unknown_label_dropped():
    engines = {"eng": fake_engine([("MISC", 0, 3)])}
    assert NerDetector(engines).detect("abc") == []


def test_entity_span_truncated_at_line_break():
    text = "John Smith\nEmail: x@y.com"
    # engine over-captures across the newline into "Email"
    engines = {"eng": fake_engine([("PERSON", 0, 16)])}
    ents = NerDetector(engines).detect(text)
    assert len(ents) == 1
    assert ents[0].text == "John Smith"
    assert ents[0].span.start == 0
    assert ents[0].span.end == 10


def test_entity_span_strips_surrounding_whitespace():
    text = "  Ahmed  "
    engines = {"eng": fake_engine([("PERSON", 0, 9)])}
    ents = NerDetector(engines).detect(text)
    assert ents[0].text == "Ahmed"
    assert ents[0].span.start == 2
    assert ents[0].span.end == 7


def test_multiple_engines_all_run():
    engines = {
        "a": fake_engine([("PERSON", 0, 3)]),
        "b": fake_engine([("ORG", 4, 7)]),
    }
    provs = {e.detector for e in NerDetector(engines).detect("abc def")}
    assert provs == {"a", "b"}
