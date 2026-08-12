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
