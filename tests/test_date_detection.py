from anonymizer.detectors.regex_rules import RegexDetector
from anonymizer.entities import EntityType


def dates(text):
    return [e.text for e in RegexDetector().detect(text) if e.type == EntityType.DATE]


def test_detects_slash_date():
    assert "17/02/2004" in dates("Date de naissance : 17/02/2004")


def test_detects_iso_date():
    assert "2004-02-17" in dates("born 2004-02-17 today")


def test_detects_dotted_date():
    assert "10.12.2025" in dates("valid 10.12.2025")


def test_dossier_number_is_not_a_date():
    assert dates("N° de dossier : MA25-47433-C01") == []
