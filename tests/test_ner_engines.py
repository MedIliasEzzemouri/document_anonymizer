from anonymizer.detectors import ner_engines


def test_default_engines_returns_dict_without_raising():
    # On a machine with no models installed this must return {} (or a subset),
    # never raise.
    engines = ner_engines.default_engines()
    assert isinstance(engines, dict)


def test_spacy_engine_missing_model_raises_cleanly():
    import pytest
    # A nonsense model name should raise (caught by default_engines), not hang.
    with pytest.raises(Exception):
        ner_engines.spacy_engine("no_such_model_xyz")
