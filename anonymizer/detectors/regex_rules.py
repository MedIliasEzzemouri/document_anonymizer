import re
from typing import Dict, Iterable, List, Optional

from anonymizer.detectors.base import Detector
from anonymizer.entities import Entity, EntityType, Span


def luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# Order matters only for readability; overlap resolution handles conflicts.
PATTERNS: Dict[EntityType, "re.Pattern"] = {
    # --- International / universal formats ---
    EntityType.EMAIL: re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # IBAN: two-letter country code + check digits + up to 30 alphanumerics.
    EntityType.IBAN: re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    # Phone: international "+<country code>..." form, OR the Moroccan local 0[5-7] form.
    EntityType.PHONE: re.compile(
        r"(?:\+\d{1,3}[ .\-]?\d(?:[ .\-]?\d){5,13}|\b0[5-7](?:[ .\-]?\d){8}\b)"
    ),
    EntityType.RIB: re.compile(r"\b\d{24}\b"),
    # First digit, then 12-18 more digits each preceded by an optional separator.
    # Separators sit *between* digits only, so the match never eats a trailing space.
    EntityType.CREDIT_CARD: re.compile(r"\b\d(?:[ \-]?\d){12,18}\b"),
    # --- National ID numbers (one entry per country; add more here) ---
    EntityType.CIN: re.compile(r"\b[A-Z]{1,2}\d{5,6}\b"),                       # Morocco
    EntityType.SSN: re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                       # USA
    EntityType.NINO: re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b"),         # UK
    EntityType.DNI: re.compile(r"(?:\b\d{8}[A-Z]\b|\b[XYZ]\d{7}[A-Z]\b)"),      # Spain (DNI/NIE)
}

# Types whose matches must pass an extra validator to count.
_VALIDATORS = {EntityType.CREDIT_CARD: luhn_valid}


class RegexDetector(Detector):
    name = "regex"

    def __init__(self, types: Optional[Iterable[EntityType]] = None):
        self.types = list(types) if types is not None else list(PATTERNS.keys())

    def detect(self, text: str) -> List[Entity]:
        found: List[Entity] = []
        for etype in self.types:
            pattern = PATTERNS[etype]
            validator = _VALIDATORS.get(etype)
            for m in pattern.finditer(text):
                value = m.group()
                if validator and not validator(value):
                    continue
                found.append(
                    Entity(
                        type=etype,
                        text=value,
                        span=Span(m.start(), m.end()),
                        detector=self.name,
                    )
                )
        return found
