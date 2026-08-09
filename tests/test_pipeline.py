from anonymizer.pipeline import anonymize_text, AnonymizationResult
from anonymizer.redactors.text_redactor import RedactionStyle
from anonymizer.entities import EntityType


def test_end_to_end_labeled():
    text = "mail a@b.com or call 0612345678"
    result = anonymize_text(text)
    assert isinstance(result, AnonymizationResult)
    assert "[EMAIL]" in result.redacted_text
    assert "[PHONE]" in result.redacted_text
    assert "a@b.com" not in result.redacted_text
    assert "0612345678" not in result.redacted_text


def test_entities_carry_replacement():
    result = anonymize_text("mail a@b.com", style=RedactionStyle.CONSISTENT)
    email = [e for e in result.entities if e.type == EntityType.EMAIL][0]
    assert email.replacement == "[EMAIL_1]"


def test_types_filter_passed_through():
    result = anonymize_text("a@b.com 0612345678", types=[EntityType.EMAIL])
    assert "0612345678" in result.redacted_text  # phone not targeted
    assert "a@b.com" not in result.redacted_text
