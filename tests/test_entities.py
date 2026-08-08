from anonymizer.entities import EntityType, Span, Entity


def test_entity_type_values_are_uppercase_strings():
    assert EntityType.EMAIL.value == "EMAIL"
    assert EntityType.CREDIT_CARD.value == "CREDIT_CARD"


def test_entity_holds_location_and_defaults():
    e = Entity(type=EntityType.EMAIL, text="a@b.com", span=Span(0, 7), detector="regex")
    assert e.span.start == 0
    assert e.span.end == 7
    assert e.score == 1.0
    assert e.replacement is None


def test_span_is_frozen():
    import dataclasses
    s = Span(1, 2)
    try:
        s.start = 5
        assert False, "Span should be immutable"
    except dataclasses.FrozenInstanceError:
        pass
