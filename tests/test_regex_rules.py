from anonymizer.detectors.regex_rules import RegexDetector, luhn_valid
from anonymizer.entities import EntityType


def types_found(text):
    return {e.type for e in RegexDetector().detect(text)}


def test_luhn_accepts_valid_card():
    assert luhn_valid("4539578763621486") is True


def test_luhn_rejects_invalid_card():
    assert luhn_valid("4539578763621487") is False


def test_detects_email():
    assert EntityType.EMAIL in types_found("write me at a.b@mail.com please")


def test_detects_moroccan_phone_plus212():
    assert EntityType.PHONE in types_found("call +212612345678")


def test_detects_moroccan_phone_local():
    assert EntityType.PHONE in types_found("call 0612345678")


def test_detects_cin():
    assert EntityType.CIN in types_found("CIN AB123456")


def test_detects_credit_card_only_if_luhn_valid():
    assert EntityType.CREDIT_CARD in types_found("card 4539578763621486")
    assert EntityType.CREDIT_CARD not in types_found("num 4539578763621487")


def test_span_matches_matched_text():
    text = "mail a.b@mail.com end"
    e = [e for e in RegexDetector().detect(text) if e.type == EntityType.EMAIL][0]
    assert text[e.span.start:e.span.end] == e.text
    assert e.detector == "regex"


def test_types_filter_limits_detection():
    d = RegexDetector(types=[EntityType.EMAIL])
    found = {e.type for e in d.detect("a@b.com and 0612345678")}
    assert found == {EntityType.EMAIL}
