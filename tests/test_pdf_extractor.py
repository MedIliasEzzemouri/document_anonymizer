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
