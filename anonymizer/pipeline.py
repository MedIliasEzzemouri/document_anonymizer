from dataclasses import dataclass
from typing import List, Optional

from anonymizer.entities import Entity, EntityType
from anonymizer.detectors.regex_rules import RegexDetector
from anonymizer.redactors.text_redactor import RedactionStyle, TextRedactor


def resolve_overlaps(entities: List[Entity]) -> List[Entity]:
    # Longest match wins: sort by start asc, then by length desc.
    ordered = sorted(entities, key=lambda e: (e.span.start, -(e.span.end - e.span.start)))
    kept: List[Entity] = []
    last_end = -1
    for e in ordered:
        if e.span.start >= last_end:
            kept.append(e)
            last_end = e.span.end
    return kept


@dataclass
class AnonymizationResult:
    redacted_text: str
    entities: List[Entity]


def anonymize_text(
    text: str,
    types: Optional[List[EntityType]] = None,
    style: RedactionStyle = RedactionStyle.LABELED,
) -> AnonymizationResult:
    detected = RegexDetector(types=types).detect(text)
    kept = resolve_overlaps(detected)
    redacted, entities = TextRedactor(style).redact(text, kept)
    return AnonymizationResult(redacted_text=redacted, entities=entities)
