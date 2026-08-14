from typing import Callable, Dict, List, Tuple

from anonymizer.detectors.base import Detector
from anonymizer.entities import Entity, EntityType, Span

# An engine takes text and returns (label, start_char, end_char) tuples.
NerEngine = Callable[[str], List[Tuple[str, int, int]]]

# Normalize each library's label vocabulary to our three named-entity types.
LABEL_MAP: Dict[str, EntityType] = {
    "PERSON": EntityType.PERSON,
    "PER": EntityType.PERSON,
    "PERS": EntityType.PERSON,
    "ORG": EntityType.ORG,
    "ORGANIZATION": EntityType.ORG,
    "LOC": EntityType.LOC,
    "LOCATION": EntityType.LOC,
    "GPE": EntityType.LOC,
}


# Common form-label / field words the small models mislabel as PERSON/LOC/ORG.
_NER_NOISE = {
    "nom", "prénom", "prenom", "date", "montant", "moyen", "numéro", "numero",
    "dossier", "adresse", "téléphone", "telephone", "tél", "tel", "email", "e-mail",
    "courriel", "paiement", "naissance", "validation", "payé", "paye", "solde",
    "name", "phone", "contact", "contacto", "credit", "card", "français", "francais",
    "elle", "first", "last", "españa", "espagne",
}


def _is_noise(value: str) -> bool:
    v = value.strip()
    return len(v) <= 2 or v.lower() in _NER_NOISE


class NerDetector(Detector):
    name = "ner"

    def __init__(self, engines: Dict[str, NerEngine]):
        self.engines = engines

    def detect(self, text: str) -> List[Entity]:
        found: List[Entity] = []
        for engine_name, engine in self.engines.items():
            for label, start, end in engine(text):
                etype = LABEL_MAP.get(label.upper())
                if etype is None:
                    continue
                start, end = self._trim(text, start, end)
                if end <= start:
                    continue  # nothing left after trimming
                if _is_noise(text[start:end]):
                    continue  # drop label/short-token false positives
                found.append(
                    Entity(
                        type=etype,
                        text=text[start:end],
                        span=Span(start, end),
                        detector=engine_name,
                    )
                )
        return found

    @staticmethod
    def _trim(text: str, start: int, end: int) -> Tuple[int, int]:
        # An entity never crosses a line break (a name doesn't span two lines).
        newline = text.find("\n", start, end)
        if newline != -1:
            end = newline
        # Strip surrounding whitespace, adjusting the span to stay accurate.
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end
