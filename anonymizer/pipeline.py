from dataclasses import dataclass
from typing import List, Optional

from anonymizer.entities import Entity, EntityType
from anonymizer.detectors.base import Detector
from anonymizer.detectors.regex_rules import RegexDetector
from anonymizer.redactors.text_redactor import RedactionStyle, TextRedactor


# ORG is detected but not redacted by default: a company name is usually not
# personal data, and the small NER models over-trigger ORG (many false positives).
# Callers can still opt in with types=[EntityType.ORG] or --types org.
DEFAULT_REDACTION_TYPES: List[EntityType] = [t for t in EntityType if t is not EntityType.ORG]


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


def detect_entities(
    text: str,
    types: Optional[List[EntityType]] = None,
    detectors: Optional[List[Detector]] = None,
) -> List[Entity]:
    if detectors is None:
        detectors = [RegexDetector(types=types)]
    found: List[Entity] = []
    for detector in detectors:
        found.extend(detector.detect(text))
    allowed = set(types) if types is not None else set(DEFAULT_REDACTION_TYPES)
    found = [e for e in found if e.type in allowed]
    return resolve_overlaps(found)


def anonymize_text(
    text: str,
    types: Optional[List[EntityType]] = None,
    style: RedactionStyle = RedactionStyle.LABELED,
    detectors: Optional[List[Detector]] = None,
) -> AnonymizationResult:
    kept = detect_entities(text, types=types, detectors=detectors)
    redacted, entities = TextRedactor(style).redact(text, kept)
    return AnonymizationResult(redacted_text=redacted, entities=entities)


def build_detectors(
    types: Optional[List[EntityType]] = None,
    use_ner: bool = False,
) -> List[Detector]:
    detectors: List[Detector] = [RegexDetector(types=types)]
    if use_ner:
        from anonymizer.detectors import ner_engines
        from anonymizer.detectors.ner_detector import NerDetector
        detectors.append(NerDetector(ner_engines.default_engines()))
    return detectors
