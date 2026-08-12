from typing import List, Tuple

WordBox = Tuple[int, int, Tuple[float, float, float, float]]


def words_to_text_and_index(words) -> Tuple[str, List["WordBox"]]:
    parts: List[str] = []
    index: List[WordBox] = []
    cursor = 0
    for w in words:
        x0, y0, x1, y1, wtext = w[0], w[1], w[2], w[3], w[4]
        if parts:
            cursor += 1  # single-space separator between words
        start = cursor
        end = start + len(wtext)
        index.append((start, end, (x0, y0, x1, y1)))
        parts.append(wtext)
        cursor = end
    return " ".join(parts), index


def rects_for_entity(entity, index) -> List[Tuple[float, float, float, float]]:
    s, e = entity.span.start, entity.span.end
    overlapping = [bbox for (cs, ce, bbox) in index if cs < e and ce > s]
    groups = {}
    for bbox in overlapping:
        key = round(bbox[1], 1)  # group words sharing a text line (same top-y)
        groups.setdefault(key, []).append(bbox)
    rects = []
    for _key, boxes in sorted(groups.items()):
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y1 = max(b[3] for b in boxes)
        rects.append((x0, y0, x1, y1))
    return rects


def entities_to_rects(entities, index) -> List[Tuple[float, float, float, float]]:
    return [r for entity in entities for r in rects_for_entity(entity, index)]
