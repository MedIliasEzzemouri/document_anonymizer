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
                found.append(
                    Entity(
                        type=etype,
                        text=text[start:end],
                        span=Span(start, end),
                        detector=engine_name,
                    )
                )
        return found
