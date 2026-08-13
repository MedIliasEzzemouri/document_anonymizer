from anonymizer.extractors.pdf_extractor import words_to_text_and_index


def test_reconstructs_text_and_char_spans():
    words = [
        (0, 0, 10, 8, "Email"),
        (12, 0, 40, 8, "a@b.com"),
    ]
    text, index = words_to_text_and_index(words)
    assert text == "Email a@b.com"
    assert index[0] == (0, 5, (0, 0, 10, 8))
    assert index[1] == (6, 13, (12, 0, 40, 8))
    # the char span really points at the word
    cs, ce, _ = index[1]
    assert text[cs:ce] == "a@b.com"


def test_empty_words_give_empty_text():
    text, index = words_to_text_and_index([])
    assert text == ""
    assert index == []


from anonymizer.extractors.pdf_extractor import rects_for_entity, entities_to_rects
from anonymizer.entities import Entity, EntityType, Span


def ent(start, end):
    return Entity(EntityType.EMAIL, "x", Span(start, end), "regex")


# index mirrors "Email a@b.com" then a second-line word "Casablanca"
INDEX = [
    (0, 5, (0.0, 0.0, 10.0, 8.0)),     # "Email"  line y=0
    (6, 13, (12.0, 0.0, 40.0, 8.0)),   # "a@b.com" line y=0
    (14, 24, (0.0, 20.0, 30.0, 28.0)), # "Casablanca" line y=20
]


def test_single_word_entity_gives_its_box():
    rects = rects_for_entity(ent(6, 13), INDEX)
    assert rects == [(12.0, 0.0, 40.0, 8.0)]


def test_multiword_same_line_unions_into_one_rect():
    # entity covers "Email a@b.com" (chars 0..13) on one line
    rects = rects_for_entity(ent(0, 13), INDEX)
    assert rects == [(0.0, 0.0, 40.0, 8.0)]


def test_entity_spanning_two_lines_gives_two_rects():
    # entity covers "a@b.com Casablanca" (chars 6..24) across two lines
    rects = rects_for_entity(ent(6, 24), INDEX)
    assert (12.0, 0.0, 40.0, 8.0) in rects
    assert (0.0, 20.0, 30.0, 28.0) in rects
    assert len(rects) == 2


def test_non_overlapping_entity_gives_no_rects():
    rects = rects_for_entity(ent(100, 110), INDEX)
    assert rects == []


def test_entities_to_rects_flattens():
    rects = entities_to_rects([ent(6, 13), ent(14, 24)], INDEX)
    assert (12.0, 0.0, 40.0, 8.0) in rects
    assert (0.0, 20.0, 30.0, 28.0) in rects
