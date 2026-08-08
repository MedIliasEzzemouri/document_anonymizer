from typing import List

from anonymizer.entities import Entity


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
