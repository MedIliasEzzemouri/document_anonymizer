from anonymizer.detectors.regex_rules import RegexDetector
from anonymizer.entities import EntityType


def types_found(text):
    return {e.type for e in RegexDetector().detect(text)}


# --- International phone numbers ---

def test_detects_us_international_phone():
    assert EntityType.PHONE in types_found("call +1 415 555 2671 now")


def test_detects_uk_international_phone():
    assert EntityType.PHONE in types_found("ring +44 20 7946 0958 please")


def test_still_detects_moroccan_local_phone():
    assert EntityType.PHONE in types_found("appelle 0612345678")


# --- National IDs, several countries ---

def test_detects_us_ssn():
    assert EntityType.SSN in types_found("SSN 123-45-6789 on file")


def test_detects_uk_nino():
    assert EntityType.NINO in types_found("NINo AB123456C recorded")


def test_detects_spain_dni():
    assert EntityType.DNI in types_found("DNI 12345678Z")


def test_detects_spain_nie():
    assert EntityType.DNI in types_found("NIE X1234567L")


def test_still_detects_moroccan_cin():
    assert EntityType.CIN in types_found("CIN AB123456 here")
