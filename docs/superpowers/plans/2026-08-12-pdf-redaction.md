# Native PDF Redaction (Slice 2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read a native-text PDF, detect PII on its text, and write a redacted PDF with the PII truly removed — reusing the existing regex + NER detection pipeline unchanged.

**Architecture:** Detection stays on plain text (char spans). A PDF layer reconstructs page text from PyMuPDF word boxes while recording a char→bbox index, maps each detected entity's char span back to page rectangles, and applies PyMuPDF redaction annotations (which delete underlying glyphs). The `Entity` model is untouched.

**Tech Stack:** Python 3.9 stdlib + `pymupdf` (a.k.a. `fitz`) + existing `anonymizer` package. `pytest` for tests.

## Global Constraints

- Python 3.9 compatible: `Optional[X]`, `List[X]`, `Tuple[...]` from `typing`; not `X | None`.
- **`Entity` model unchanged** — no `region` field; char→box mapping lives in the PDF layer.
- **`fitz` is imported lazily** (inside functions/methods), never at module top, so importing the package/CLI stays light and offline-testable.
- **Pure mapping functions** (`words_to_text_and_index`, `rects_for_entity`) take plain tuples and are unit-tested without PyMuPDF.
- **True removal by default:** `SECURE`/`LABELED` use `add_redact_annot` + `apply_redactions`; `COVER` only draws a box (insecure) and warns.
- Everything runs local, no API keys.
- Every task ends green (`python3 -m pytest -q -m "not slow"`) and is committed.

---

## File Structure

- `anonymizer/extractors/__init__.py` — package marker. (Task 1)
- `anonymizer/extractors/pdf_extractor.py` — `words_to_text_and_index`, `rects_for_entity`, `extract_page_words`. (Tasks 1–2)
- `anonymizer/pipeline.py` — add `detect_entities`, rewrite `anonymize_text` to use it. (Task 3)
- `anonymizer/redactors/pdf_redactor.py` — `PdfRedactionMode`, `PdfRedactor`. (Task 4)
- `anonymizer/cli.py` — route `.pdf` inputs, add `--pdf-mode`. (Task 5)
- `requirements.txt` — add `pymupdf`. (Task 4)
- `tests/test_pdf_extractor.py` (offline), `tests/test_pipeline_detect.py` (offline), `tests/test_pdf_redactor.py` (integration), `tests/test_cli_pdf.py` (offline via fake). (Tasks 1–5)

---

## Task 1: Word→text reconstruction with char index

**Files:**
- Create: `anonymizer/extractors/__init__.py` (empty), `anonymizer/extractors/pdf_extractor.py`
- Test: `tests/test_pdf_extractor.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `WordBox = Tuple[int, int, Tuple[float, float, float, float]]` and
  `words_to_text_and_index(words) -> Tuple[str, List[WordBox]]`. `words` is a list of tuples whose
  first five elements are `(x0, y0, x1, y1, text)` (PyMuPDF's `get_text("words")` shape). Joins word
  texts with single spaces; each `WordBox` is `(char_start, char_end, (x0,y0,x1,y1))`.

- [ ] **Step 1: Write the failing test**

`tests/test_pdf_extractor.py`:
```python
from anonymizer.extractors.pdf_extractor import words_to_text_and_index


def test_reconstructs_text_and_char_spans():
    words = [
        (0, 0, 10, 8, "Email"),
        (12, 0, 40, 8, "a@b.com"),
    ]
    text, index = words_to_text_and_index(words)
    assert text == "Email a@b.com"
    assert index[0] == (0, 5, (0, 0, 10, 8))
    assert index[1] == (6, 13, (12, 0, 40, 8))
    # the char span really points at the word
    cs, ce, _ = index[1]
    assert text[cs:ce] == "a@b.com"


def test_empty_words_give_empty_text():
    text, index = words_to_text_and_index([])
    assert text == ""
    assert index == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pdf_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.extractors.pdf_extractor'`.

- [ ] **Step 3: Write minimal implementation**

Create empty `anonymizer/extractors/__init__.py`.

`anonymizer/extractors/pdf_extractor.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pdf_extractor.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/extractors/__init__.py anonymizer/extractors/pdf_extractor.py tests/test_pdf_extractor.py
git commit -m "feat: PDF word->text reconstruction with char index"
```

---

## Task 2: Map entity char spans to page rectangles

**Files:**
- Modify: `anonymizer/extractors/pdf_extractor.py`
- Test: `tests/test_pdf_extractor.py` (add tests)

**Interfaces:**
- Consumes: `Entity`/`Span` from `anonymizer.entities`; `WordBox` list from Task 1.
- Produces: `rects_for_entity(entity, index) -> List[Tuple[float,float,float,float]]` — the words whose
  char range intersects the entity's span, grouped per text line (shared rounded `y0`), each group
  unioned into one rectangle. Also `entities_to_rects(entities, index)` = flattened over all entities.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pdf_extractor.py`:
```python
from anonymizer.extractors.pdf_extractor import rects_for_entity, entities_to_rects
from anonymizer.entities import Entity, EntityType, Span


def ent(start, end):
    return Entity(EntityType.EMAIL, "x", Span(start, end), "regex")


# index mirrors "Email a@b.com" then a second-line word "Casablanca"
INDEX = [
    (0, 5, (0.0, 0.0, 10.0, 8.0)),     # "Email"  line y=0
    (6, 13, (12.0, 0.0, 40.0, 8.0)),   # "a@b.com" line y=0
    (14, 24, (0.0, 20.0, 30.0, 28.0)), # "Casablanca" line y=20
]


def test_single_word_entity_gives_its_box():
    rects = rects_for_entity(ent(6, 13), INDEX)
    assert rects == [(12.0, 0.0, 40.0, 8.0)]


def test_multiword_same_line_unions_into_one_rect():
    # entity covers "Email a@b.com" (chars 0..13) on one line
    rects = rects_for_entity(ent(0, 13), INDEX)
    assert rects == [(0.0, 0.0, 40.0, 8.0)]


def test_entity_spanning_two_lines_gives_two_rects():
    # entity covers "a@b.com Casablanca" (chars 6..24) across two lines
    rects = rects_for_entity(ent(6, 24), INDEX)
    assert (12.0, 0.0, 40.0, 8.0) in rects
    assert (0.0, 20.0, 30.0, 28.0) in rects
    assert len(rects) == 2


def test_non_overlapping_entity_gives_no_rects():
    rects = rects_for_entity(ent(100, 110), INDEX)
    assert rects == []


def test_entities_to_rects_flattens():
    rects = entities_to_rects([ent(6, 13), ent(14, 24)], INDEX)
    assert (12.0, 0.0, 40.0, 8.0) in rects
    assert (0.0, 20.0, 30.0, 28.0) in rects
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pdf_extractor.py -v`
Expected: FAIL — `ImportError: cannot import name 'rects_for_entity'`.

- [ ] **Step 3: Write minimal implementation**

Append to `anonymizer/extractors/pdf_extractor.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pdf_extractor.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/extractors/pdf_extractor.py tests/test_pdf_extractor.py
git commit -m "feat: map entity char spans to page rectangles"
```

---

## Task 3: Extract detect_entities from the pipeline

**Files:**
- Modify: `anonymizer/pipeline.py`
- Test: `tests/test_pipeline_detect.py`

**Interfaces:**
- Consumes: `RegexDetector`, `NerDetector`, `resolve_overlaps`, `DEFAULT_REDACTION_TYPES`, `Detector`, `Entity`, `EntityType`.
- Produces: `detect_entities(text, types=None, detectors=None) -> List[Entity]` — runs detectors,
  filters by `types` (default excludes ORG), resolves overlaps. `anonymize_text` is rewritten to call it.

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline_detect.py`:
```python
from anonymizer.pipeline import detect_entities
from anonymizer.detectors.ner_detector import NerDetector
from anonymizer.entities import EntityType


def fake_engine(spans):
    def run(text):
        return list(spans)
    return run


def test_detect_entities_finds_regex_pii():
    ents = detect_entities("mail a@b.com")
    assert any(e.type == EntityType.EMAIL for e in ents)


def test_detect_entities_excludes_org_by_default():
    ner = NerDetector({"e": fake_engine([("ORG", 0, 4)])})
    ents = detect_entities("ACME hires", detectors=[ner])
    assert all(e.type != EntityType.ORG for e in ents)


def test_detect_entities_resolves_overlaps():
    # two detectors emitting the same email span -> deduped to one
    ents = detect_entities("mail a@b.com")
    emails = [e for e in ents if e.type == EntityType.EMAIL]
    assert len(emails) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pipeline_detect.py -v`
Expected: FAIL — `ImportError: cannot import name 'detect_entities'`.

- [ ] **Step 3: Write minimal implementation**

In `anonymizer/pipeline.py`, add `detect_entities` and rewrite `anonymize_text` to use it (keep
`resolve_overlaps`, `DEFAULT_REDACTION_TYPES`, `AnonymizationResult`, `build_detectors` as they are):
```python
def detect_entities(
    text: str,
    types: Optional[List[EntityType]] = None,
    detectors: Optional[List[Detector]] = None,
) -> List[Entity]:
    if detectors is None:
        detectors = [RegexDetector(types=types)]
    found: List[Entity] = []
    for detector in detectors:
        found.extend(detector.detect(text))
    allowed = set(types) if types is not None else set(DEFAULT_REDACTION_TYPES)
    found = [e for e in found if e.type in allowed]
    return resolve_overlaps(found)


def anonymize_text(
    text: str,
    types: Optional[List[EntityType]] = None,
    style: RedactionStyle = RedactionStyle.LABELED,
    detectors: Optional[List[Detector]] = None,
) -> AnonymizationResult:
    kept = detect_entities(text, types=types, detectors=detectors)
    redacted, entities = TextRedactor(style).redact(text, kept)
    return AnonymizationResult(redacted_text=redacted, entities=entities)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pipeline_detect.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run full suite (anonymize_text refactor is behavior-preserving)**

Run: `python3 -m pytest -q -m "not slow"`
Expected: all prior tests still pass.

- [ ] **Step 6: Commit**

```bash
git add anonymizer/pipeline.py tests/test_pipeline_detect.py
git commit -m "refactor: extract detect_entities shared by text and PDF"
```

---

## Task 4: PdfRedactor (PyMuPDF integration)

**Files:**
- Create: `anonymizer/redactors/pdf_redactor.py`
- Modify: `anonymizer/extractors/pdf_extractor.py` (add `extract_page_words`), `requirements.txt`
- Test: `tests/test_pdf_redactor.py`

**Interfaces:**
- Consumes: `words_to_text_and_index`, `rects_for_entity`, `detect_entities`, `build_detectors`.
- Produces:
  - `extract_page_words(page) -> list` (thin `page.get_text("words")` wrapper).
  - `class PdfRedactionMode(str, Enum)`: `SECURE="secure"`, `LABELED="labeled"`, `COVER="cover"`.
  - `class PdfRedactor` — `__init__(self, mode=PdfRedactionMode.SECURE, types=None, use_ner=False)`;
    `redact(self, in_path: str, out_path: str) -> dict` returning
    `{"source", "mode", "entities": [{"type","page","bbox","detector"}], "counts": {type: n}}`.

- [ ] **Step 1: Write the failing test (integration, needs fitz)**

`tests/test_pdf_redactor.py`:
```python
import pytest

fitz = pytest.importorskip("fitz")


def _make_pdf(path, body):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), body, fontsize=11)
    doc.save(str(path))
    doc.close()


@pytest.mark.slow
def test_secure_mode_removes_pii_from_output(tmp_path):
    from anonymizer.redactors.pdf_redactor import PdfRedactor, PdfRedactionMode

    src = tmp_path / "in.pdf"
    out = tmp_path / "out.pdf"
    _make_pdf(src, "Email a@b.com here")

    audit = PdfRedactor(mode=PdfRedactionMode.SECURE).redact(str(src), str(out))

    reopened = fitz.open(str(out))
    text = "".join(p.get_text() for p in reopened)
    reopened.close()
    assert "a@b.com" not in text                    # truly removed
    assert audit["counts"].get("EMAIL", 0) >= 1
    assert audit["entities"][0]["page"] == 0


@pytest.mark.slow
def test_cover_mode_keeps_text(tmp_path):
    from anonymizer.redactors.pdf_redactor import PdfRedactor, PdfRedactionMode

    src = tmp_path / "in.pdf"
    out = tmp_path / "out.pdf"
    _make_pdf(src, "Email a@b.com here")

    PdfRedactor(mode=PdfRedactionMode.COVER).redact(str(src), str(out))

    reopened = fitz.open(str(out))
    text = "".join(p.get_text() for p in reopened)
    reopened.close()
    assert "a@b.com" in text                          # cover mode leaves text (insecure)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pdf_redactor.py -v -m slow`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.redactors.pdf_redactor'`
(or skip if `fitz` not yet installed — install in Step 3).

- [ ] **Step 3: Add dependency + implementation**

Append to `requirements.txt`:
```
# Slice 2b — native PDF read/redact
pymupdf
```
Install into the venv: `.venv/bin/python -m pip install pymupdf`.

Add to `anonymizer/extractors/pdf_extractor.py`:
```python
def extract_page_words(page):
    # PyMuPDF: list of (x0, y0, x1, y1, word, block, line, word_no)
    return page.get_text("words")
```

`anonymizer/redactors/pdf_redactor.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_pdf_redactor.py -v -m slow`
Expected: PASS (2 passed).

- [ ] **Step 5: Confirm offline suite still green (integration deselected)**

Run: `python3 -m pytest -q -m "not slow"`
Expected: all pass (the fitz tests are marked slow and skipped).

- [ ] **Step 6: Commit**

```bash
git add anonymizer/redactors/pdf_redactor.py anonymizer/extractors/pdf_extractor.py \
        requirements.txt tests/test_pdf_redactor.py
git commit -m "feat: PdfRedactor with secure/labeled/cover modes"
```

---

## Task 5: CLI routing for PDF inputs

**Files:**
- Modify: `anonymizer/cli.py`
- Test: `tests/test_cli_pdf.py`

**Interfaces:**
- Consumes: `PdfRedactor`, `PdfRedactionMode`, `_parse_types`, `build_audit_log`-style output.
- Produces: `.pdf` inputs route to `PdfRedactor`; new `--pdf-mode secure|labeled|cover` (default
  `secure`); `--out` defaults to `<stem>_redacted.pdf`; audit written to `--audit` if given.

- [ ] **Step 1: Write the failing test (offline via a fake redactor)**

`tests/test_cli_pdf.py`:
```python
import json


def test_pdf_input_routes_to_redactor(tmp_path, monkeypatch):
    import anonymizer.cli as cli

    calls = {}

    class FakeRedactor:
        def __init__(self, mode=None, types=None, use_ner=False):
            calls["mode"] = mode

        def redact(self, in_path, out_path):
            with open(out_path, "w") as fh:
                fh.write("%PDF-fake")
            calls["out"] = out_path
            return {"source": in_path, "mode": "secure",
                    "entities": [], "counts": {"EMAIL": 1}}

    monkeypatch.setattr(cli, "PdfRedactor", FakeRedactor)

    src = tmp_path / "doc.pdf"
    src.write_text("dummy")
    audit = tmp_path / "log.json"

    code = cli.main([str(src), "--pdf-mode", "secure", "--audit", str(audit)])

    assert code == 0
    assert calls["out"].endswith("doc_redacted.pdf")
    assert json.loads(audit.read_text())["counts"] == {"EMAIL": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli_pdf.py -v`
Expected: FAIL — `AttributeError: module 'anonymizer.cli' has no attribute 'PdfRedactor'`
(or argparse error on `--pdf-mode`).

- [ ] **Step 3: Write minimal implementation**

In `anonymizer/cli.py`:

Add imports near the top:
```python
import os
from anonymizer.redactors.pdf_redactor import PdfRedactor, PdfRedactionMode
```

Add the flag in `build_parser()` (after `--ner`):
```python
    p.add_argument("--pdf-mode", default="secure",
                   choices=[m.value for m in PdfRedactionMode],
                   help="PDF redaction appearance (default: secure)")
```

In `main()`, branch on the extension before the text flow:
```python
    if args.input.lower().endswith(".pdf"):
        out_path = args.out or _default_pdf_out(args.input)
        redactor = PdfRedactor(
            mode=PdfRedactionMode(args.pdf_mode),
            types=_parse_types(args.types),
            use_ner=args.ner,
        )
        audit = redactor.redact(args.input, out_path)
        if args.audit:
            with open(args.audit, "w", encoding="utf-8") as fh:
                json.dump(audit, fh, ensure_ascii=False, indent=2)
        sys.stdout.write("Redacted PDF written to {}\n".format(out_path))
        return 0
```

Add the helper near `_parse_types`:
```python
def _default_pdf_out(path: str) -> str:
    stem, _ext = os.path.splitext(path)
    return stem + "_redacted.pdf"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli_pdf.py -v`
Expected: PASS.

- [ ] **Step 5: Run full offline suite**

Run: `python3 -m pytest -q -m "not slow"`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add anonymizer/cli.py tests/test_cli_pdf.py
git commit -m "feat: route PDF inputs through PdfRedactor CLI flag"
```

---

## Task 6: Real-corpus smoke test

**Files:** none (manual verification).

- [ ] **Step 1: Redact a real English PDF (secure) and confirm removal**

Run:
```bash
.venv/bin/python -m anonymizer "Pdf_test/01_cv_en_sarah_mitchell.pdf" --ner \
    --audit /tmp/cv_audit.json
.venv/bin/python -c "import fitz,sys; d=fitz.open('Pdf_test/01_cv_en_sarah_mitchell_redacted.pdf'); t=''.join(p.get_text() for p in d); print('leaked email?', '@' in t and 'sarah' in t.lower())"
```
Expected: the redacted PDF is written; audit JSON lists PERSON/EMAIL/PHONE entities with page+bbox.

- [ ] **Step 2: Spot-check a French and an Arabic doc**

Run:
```bash
.venv/bin/python -m anonymizer "Pdf_test/06_bank_statement_en_emily_thompson.pdf" --ner --audit /tmp/bank.json
.venv/bin/python -m anonymizer "Pdf_test/08_bank_kashf_ar_ahmed_bensalem.pdf" --audit /tmp/ar.json
```
Expected: EN/FR redact names + structured PII; the Arabic doc redacts structured PII (IBAN/phone) but not Arabic names (CAMeL not installed) — confirms the documented 2c gap.

- [ ] **Step 3: No commit (verification only).** Note findings for the merge summary.

---

## Self-Review

**Spec coverage:**
- Extract text + word coordinates → Task 1 (`words_to_text_and_index`) + Task 4 (`extract_page_words`) ✓
- Map entity char spans → page rectangles → Task 2 (`rects_for_entity`/`entities_to_rects`) ✓
- `Entity` model unchanged (mapping external) → Tasks 1–2 ✓
- Reuse detection pipeline via `detect_entities` → Task 3 ✓
- True removal default + 3 modes (secure/labeled/cover) → Task 4 (`PdfRedactor`) ✓
- Per-page detection → Task 4 (loop over pages) ✓
- CLI `.pdf` routing + `--pdf-mode` + default `<stem>_redacted.pdf` + audit → Task 5 ✓
- `pymupdf` dependency, lazy `fitz` import → Task 4 (import inside `redact`) ✓
- Offline pure tests + integration tests → Tasks 1–2/5 offline, Task 4 integration ✓
- Real corpus verification → Task 6 ✓
- COVER warning about retained text → Task 4 (`sys.stderr.write`) ✓

**Type consistency:** `WordBox`, `words_to_text_and_index`, `rects_for_entity`, `entities_to_rects`,
`extract_page_words`, `detect_entities(text, types, detectors)`, `PdfRedactionMode`,
`PdfRedactor(mode, types, use_ner).redact(in_path, out_path) -> dict` are consistent across
producing (Tasks 1–4) and consuming (Tasks 4–5) tasks. `_default_pdf_out` and `_parse_types` are
both defined/used in Task 5.

**Placeholder scan:** No TBD/TODO; every code step has runnable code and exact commands.
