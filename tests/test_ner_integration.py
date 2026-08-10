import pytest

spacy = pytest.importorskip("spacy")


@pytest.mark.slow
def test_real_spacy_en_finds_person():
    try:
        nlp_check = spacy.load("en_core_web_sm")
    except Exception:
        pytest.skip("en_core_web_sm not installed")
    del nlp_check

    from anonymizer.detectors.ner_engines import spacy_engine
    from anonymizer.detectors.ner_detector import NerDetector
    from anonymizer.entities import EntityType

    text = "Barack Obama visited Paris."
    det = NerDetector({"spacy-en": spacy_engine("en_core_web_sm")})
    ents = det.detect(text)
    types = {e.type for e in ents}
    assert EntityType.PERSON in types
    person = [e for e in ents if e.type == EntityType.PERSON][0]
    assert text[person.span.start:person.span.end] == person.text
