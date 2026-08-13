import sys
from collections import Counter
from enum import Enum
from typing import List, Optional

from anonymizer.entities import EntityType
from anonymizer.extractors.pdf_extractor import (
    extract_page_words,
    rects_for_entity,
    words_to_text_and_index,
)
from anonymizer.pipeline import build_detectors, detect_entities


class PdfRedactionMode(str, Enum):
    SECURE = "secure"
    LABELED = "labeled"
    COVER = "cover"


class PdfRedactor:
    def __init__(self, mode: PdfRedactionMode = PdfRedactionMode.SECURE,
                 types: Optional[List[EntityType]] = None, use_ner: bool = False):
        self.mode = mode
        self.types = types
        self.use_ner = use_ner

    def redact(self, in_path: str, out_path: str) -> dict:
        import fitz  # lazy: keep module import light and offline-testable

        doc = fitz.open(in_path)
        audit_entities = []
        for pno in range(len(doc)):
            page = doc[pno]
            words = extract_page_words(page)
            text, index = words_to_text_and_index(words)
            detectors = build_detectors(types=self.types, use_ner=self.use_ner)
            entities = detect_entities(text, types=self.types, detectors=detectors)
            for e in entities:
                for rect in rects_for_entity(e, index):
                    r = fitz.Rect(rect)
                    if self.mode == PdfRedactionMode.COVER:
                        page.draw_rect(r, fill=(0, 0, 0), color=(0, 0, 0))
                    elif self.mode == PdfRedactionMode.LABELED:
                        page.add_redact_annot(r, text=e.type.value,
                                              fill=(0, 0, 0), text_color=(1, 1, 1))
                    else:  # SECURE
                        page.add_redact_annot(r, fill=(0, 0, 0))
                    audit_entities.append({
                        "type": e.type.value, "page": pno,
                        "bbox": rect, "detector": e.detector,
                    })
            if self.mode != PdfRedactionMode.COVER:
                page.apply_redactions()

        if self.mode == PdfRedactionMode.COVER:
            sys.stderr.write(
                "WARNING: cover mode draws boxes but leaves the PII in the file "
                "(still extractable). Use secure mode for a shareable document.\n")

        doc.save(out_path)
        doc.close()
        counts = Counter(x["type"] for x in audit_entities)
        return {"source": in_path, "mode": self.mode.value,
                "entities": audit_entities, "counts": dict(counts)}
