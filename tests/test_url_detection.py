from anonymizer.detectors.regex_rules import RegexDetector
from anonymizer.entities import EntityType


def found(text):
    return [e for e in RegexDetector().detect(text) if e.type == EntityType.URL]


def test_detects_bare_profile_url_with_path():
    # the LinkedIn-handle leak we found in the real CV
    hits = found("profile linkedin.com/in/sarahmitchell89 here")
    assert hits
    assert hits[0].text == "linkedin.com/in/sarahmitchell89"


def test_detects_https_url():
    hits = found("see https://github.com/med/anonymizer for code")
    assert hits and hits[0].text == "https://github.com/med/anonymizer"


def test_detects_www_url():
    hits = found("visit www.example.com/profile now")
    assert hits and hits[0].text.startswith("www.example.com/profile")


def test_does_not_match_bare_domain_without_path():
    # a plain company domain is not a personal identifier -> skip to avoid over-redaction
    assert found("email host is example.com only") == []


def test_does_not_swallow_an_email():
    hits = found("mail a.b@example.com please")
    assert hits == []
