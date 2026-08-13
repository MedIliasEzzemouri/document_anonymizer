# Slice 2b — Native PDF Read + Coordinate-Aware Redaction Design

**Date:** 2026-08-12
**Status:** Approved
**Scope:** Read native-text PDFs, detect PII on the extracted text, and write a redacted
PDF with the PII removed. Reuses the Slice 1/2a detection pipeline unchanged.

## Goal

`PDF in → extract text + word coordinates → detect (existing regex + NER) → map entities to
page rectangles → write redacted PDF + audit log`. The `Entity` model stays text-based; the
mapping from character spans to page rectangles lives in a PDF-specific layer.

## Non-goals (later slices)

- OCR / scanned-image PDFs → Slice 3 (these PDFs are native text, no OCR needed)
- Arabic NER (CAMeL) → Slice 2c (structured PII still redacts in Arabic docs; Arabic *names* do not yet)
- Transformer NER upgrades (CamemBERT, en_core_web_trf, GLiNER) → later "model foundation" slice (needs PyTorch)
- Document-type classifier → its own later slice
- Streamlit UI → Slice 4

## Success criteria

- `python -m anonymizer file.pdf` writes `<name>_redacted.pdf` with PII removed.
- In `secure` mode the PII is **gone from the output's extractable text** (true removal, not a visual cover).
- `--pdf-mode secure|labeled|cover` selects appearance; default `secure`.
- Structured PII (email, phone, IBAN, IDs, card) redacts across EN/FR/AR docs; EN/FR names too.
- Pure mapping logic is unit-tested offline (no PyMuPDF); real PDF read/redact covered by integration tests.

## Key decisions

- **Entity model unchanged.** Detection stays on plain text (char spans). The char→box map is
  held in the PDF layer, so no `region` field is added to `Entity` (YAGNI).
- **True removal by default.** Use PyMuPDF redaction annotations (`add_redact_annot` +
  `apply_redactions`), which delete underlying glyphs — a drawn black box alone leaves the PII
  extractable, which would be a leak for a privacy tool.
- **Three appearance modes** (`PdfRedactionMode`): `SECURE` (remove + black box, default),
  `LABELED` (remove + black box + entity-type text), `COVER` (draw box, keep text — insecure,
  emits a warning; for quick visual previews only).
- **Per-page detection.** Each page's text + word boxes are independent; entities don't cross pages.

## New / changed files

- `anonymizer/extractors/__init__.py` — package marker. (create)
- `anonymizer/extractors/pdf_extractor.py` — pure mapping functions + a thin fitz word reader. (create)
- `anonymizer/redactors/pdf_redactor.py` — `PdfRedactionMode`, `PdfRedactor`. (create)
- `anonymizer/pipeline.py` — extract `detect_entities(...)` reused by text + PDF. (modify)
- `anonymizer/cli.py` — route `.pdf` inputs to the PDF flow; add `--pdf-mode`. (modify)
- `requirements.txt` — add `pymupdf`. (modify)
- `tests/test_pdf_extractor.py` (offline), `tests/test_pdf_redactor.py` (integration, importorskip fitz). (create)

## Extraction & mapping (`extractors/pdf_extractor.py`)

A "word" is PyMuPDF's `page.get_text("words")` tuple: `(x0, y0, x1, y1, text, block, line, word_no)`.

```python
WordBox = Tuple[int, int, Tuple[float, float, float, float]]  # (char_start, char_end, bbox)

def words_to_text_and_index(words) -> Tuple[str, List[WordBox]]:
    # Join word texts with single spaces; record each word's char span + bbox.
    # Returns the reconstructed page text and the per-word index.

def entities_to_rects(entities, index) -> List[Tuple[float, float, float, float]]:
    # For each entity char span, collect words whose char range intersects it,
    # group by text line (shared y), and union each group's bboxes into one rect.

def extract_page_words(page) -> list:   # thin fitz wrapper: page.get_text("words")
```

`words_to_text_and_index` and `entities_to_rects` are **pure** (operate on plain tuples), so they
are fully unit-tested without PyMuPDF. Detection runs on the *reconstructed* text, and the same
word index maps entity char spans back to boxes — internally consistent.

## Redactor (`redactors/pdf_redactor.py`)

```python
class PdfRedactionMode(str, Enum):
    SECURE = "secure"
    LABELED = "labeled"
    COVER = "cover"

class PdfRedactor:
    def __init__(self, mode: PdfRedactionMode = PdfRedactionMode.SECURE,
                 types=None, use_ner=False): ...
    def redact(self, in_path: str, out_path: str) -> dict:
        # For each page: extract words -> (text, index); detect_entities(text, ...);
        # entities_to_rects -> rectangles. SECURE/LABELED: add_redact_annot(rect,
        # fill=black[, text=type]) then page.apply_redactions(). COVER: draw_rect filled
        # black, no apply_redactions (warn: text retained). Save out_path.
        # Return an audit dict incl. per-entity type, page index, bbox, detector.
```

## Pipeline refactor (`pipeline.py`)

Extract the detect→filter→overlap-resolve core so both entry points share it:

```python
def detect_entities(text, types=None, detectors=None) -> List[Entity]:
    if detectors is None:
        detectors = [RegexDetector(types=types)]
    found = []
    for d in detectors:
        found.extend(d.detect(text))
    allowed = set(types) if types is not None else set(DEFAULT_REDACTION_TYPES)
    found = [e for e in found if e.type in allowed]
    return resolve_overlaps(found)
```

`anonymize_text` is rewritten to call `detect_entities` then redact — behavior unchanged.

## CLI (`cli.py`)

- If `input` ends with `.pdf` (case-insensitive) → PDF flow: build a `PdfRedactor(mode, types,
  use_ner)`, write to `--out` (default `<name>_redacted.pdf`), write `--audit` if given.
- New `--pdf-mode secure|labeled|cover` (default `secure`). Text `--style` is ignored for PDFs.
- Non-PDF inputs use the existing text flow.

## Dependency & error handling

- Adds `pymupdf` (clean wheel, no PyTorch). One-time `pip install pymupdf`.
- Encrypted/unreadable PDF → caught, clear message, non-zero exit.
- `COVER` mode prints a stderr warning that the PII remains extractable.
- Empty pages produce no entities and are passed through unchanged.

## Testing

**Offline (pure, no PyMuPDF):**
- `words_to_text_and_index`: char spans + bboxes correct for a synthetic word list.
- `entities_to_rects`: a single-word entity → its box; a multi-word entity on one line → unioned rect; entity spanning two lines → two rects; non-overlapping entity → no rect.

**Integration (`importorskip fitz`):**
- Build a small PDF in-test (`fitz` + `insert_text`) containing `a@b.com`. Redact in `SECURE`
  mode; reopen; assert `a@b.com` is **absent** from `page.get_text()` (true removal).
- `COVER` mode: assert the text is still present but a redaction rectangle was drawn.
