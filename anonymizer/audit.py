import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import List

from anonymizer.entities import Entity


def build_audit_log(
    source: str,
    style: str,
    entities: List[Entity],
    redact_audit: bool = False,
) -> dict:
    def original_of(e: Entity) -> str:
        if redact_audit:
            return hashlib.sha256(e.text.encode("utf-8")).hexdigest()
        return e.text

    entries = [
        {
            "type": e.type.value,
            "original": original_of(e),
            "replacement": e.replacement,
            "start": e.span.start,
            "end": e.span.end,
            "detector": e.detector,
            "score": e.score,
        }
        for e in entities
    ]
    counts = Counter(e.type.value for e in entities)
    return {
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "style": style,
        "entities": entries,
        "counts": dict(counts),
    }
