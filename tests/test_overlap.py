from anonymizer.pipeline import resolve_overlaps
from anonymizer.entities import Entity, EntityType, Span


def make(start, end, etype=EntityType.PHONE):
    return Entity(etype, "x", Span(start, end), "regex")


def test_keeps_longer_of_two_overlapping():
    short = make(0, 5)
    longer = make(0, 10)
    kept = resolve_overlaps([short, longer])
    assert kept == [longer]


def test_keeps_non_overlapping_sorted_by_start():
    a = make(10, 15)
    b = make(0, 5)
    kept = resolve_overlaps([a, b])
    assert [e.span.start for e in kept] == [0, 10]


def test_drops_later_entity_overlapping_kept_one():
    first = make(0, 10)
    overlapping = make(5, 8)
    kept = resolve_overlaps([first, overlapping])
    assert kept == [first]
