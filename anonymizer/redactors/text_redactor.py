from enum import Enum
from typing import Dict, List, Tuple

from anonymizer.entities import Entity


class RedactionStyle(str, Enum):
    LABELED = "labeled"
    CONSISTENT = "consistent"
    BLACKOUT = "blackout"
    REMOVE = "remove"


class TextRedactor:
    def __init__(self, style: RedactionStyle):
        self.style = style

    def _replacement(self, entity: Entity, counters: Dict, seen: Dict) -> str:
        if self.style == RedactionStyle.LABELED:
            return "[{}]".format(entity.type.value)
        if self.style == RedactionStyle.CONSISTENT:
            key = (entity.type, entity.text.strip().lower())
            if key not in seen:
                counters[entity.type] = counters.get(entity.type, 0) + 1
                seen[key] = counters[entity.type]
            return "[{}_{}]".format(entity.type.value, seen[key])
        if self.style == RedactionStyle.BLACKOUT:
            return "█" * len(entity.text)
        if self.style == RedactionStyle.REMOVE:
            return ""
        raise ValueError("unknown style: {}".format(self.style))

    def redact(self, text: str, entities: List[Entity]) -> Tuple[str, List[Entity]]:
        counters: Dict = {}
        seen: Dict = {}
        # Assign replacements left-to-right so CONSISTENT numbering follows reading order.
        ordered = sorted(entities, key=lambda e: e.span.start)
        for e in ordered:
            e.replacement = self._replacement(e, counters, seen)
        # Apply right-to-left so earlier offsets stay valid.
        result = text
        for e in sorted(ordered, key=lambda e: e.span.start, reverse=True):
            result = result[: e.span.start] + e.replacement + result[e.span.end :]
        return result, ordered
