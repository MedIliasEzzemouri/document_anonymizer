from anonymizer.redactors.text_redactor import RedactionStyle, TextRedactor
from anonymizer.entities import Entity, EntityType, Span


def ents(text):
    # two emails, one repeated value
    return [
        Entity(EntityType.EMAIL, "a@b.com", Span(0, 7), "regex"),
        Entity(EntityType.EMAIL, "a@b.com", Span(12, 19), "regex"),
    ]


BASE = "a@b.com and a@b.com"


def test_labeled_style():
    red = TextRedactor(RedactionStyle.LABELED)
    out, entities = red.redact(BASE, ents(BASE))
    assert out == "[EMAIL] and [EMAIL]"
    assert entities[0].replacement == "[EMAIL]"


def test_consistent_style_reuses_token_for_same_value():
    red = TextRedactor(RedactionStyle.CONSISTENT)
    out, _ = red.redact(BASE, ents(BASE))
    assert out == "[EMAIL_1] and [EMAIL_1]"


def test_consistent_style_numbers_distinct_values():
    text = "a@b.com and c@d.com"
    entities = [
        Entity(EntityType.EMAIL, "a@b.com", Span(0, 7), "regex"),
        Entity(EntityType.EMAIL, "c@d.com", Span(12, 19), "regex"),
    ]
    out, _ = TextRedactor(RedactionStyle.CONSISTENT).redact(text, entities)
    assert out == "[EMAIL_1] and [EMAIL_2]"


def test_blackout_style_matches_length():
    red = TextRedactor(RedactionStyle.BLACKOUT)
    out, _ = red.redact(BASE, ents(BASE))
    assert out == "███████ and ███████"


def test_remove_style_deletes_span():
    red = TextRedactor(RedactionStyle.REMOVE)
    out, _ = red.redact(BASE, ents(BASE))
    assert out == " and "
