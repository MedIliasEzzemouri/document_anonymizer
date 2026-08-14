from anonymizer.detectors.label_rules import LabelDetector
from anonymizer.entities import EntityType


def by_type(text):
    out = {}
    for e in LabelDetector().detect(text):
        out.setdefault(e.type, []).append(e.text)
    return out


# The exact structured form that leaked (space-joined, as PDF extraction yields it).
FORM = ("Nom : EZZEMOURI Prénom : Mohamed Ilias "
        "Date de naissance : 17/02/2004 N° de dossier : MA25-47433-C01 "
        "Montant payé : 1 900 dirhams")


def test_catches_surname_after_nom():
    got = by_type(FORM)
    assert "EZZEMOURI" in got[EntityType.PERSON]


def test_catches_firstname_after_prenom():
    assert "Mohamed Ilias" in by_type(FORM)[EntityType.PERSON]


def test_catches_birthdate_as_date():
    assert "17/02/2004" in by_type(FORM)[EntityType.DATE]


def test_catches_dossier_as_ref():
    assert "MA25-47433-C01" in by_type(FORM)[EntityType.REF]


def test_span_points_at_value():
    e = [e for e in LabelDetector().detect(FORM) if e.text == "EZZEMOURI"][0]
    assert FORM[e.span.start:e.span.end] == "EZZEMOURI"
    assert e.detector == "label"


def test_english_label():
    got = by_type("Name : SMITH Date of birth : 1990-01-01")
    assert "SMITH" in got[EntityType.PERSON]
    assert "1990-01-01" in got[EntityType.DATE]
