# Document Anonymizer — Roadmap

A local, zero-API PII redaction tool: takes a PDF / image / text / DOCX, finds every piece
of personal information, redacts it, and returns a shareable file plus a JSON audit log.
**International by design** — universal formats (email, phone, IBAN, credit card) work
worldwide, and national-ID support is a per-country registry (Morocco, USA, UK, Spain
today; easy to extend). Relevant to GDPR (EU) and Law 09-08 (Morocco).

The project is built in **vertical slices**. Each slice ends with something that runs, and
each plugs into the shared `Entity` spine established in slice 1 without reworking the core.
Every slice gets its own spec → plan → implementation cycle.

## Architecture spine

The whole system is a pipeline around one data model:

```
ingest → extract (text + location) → detect (entities) → resolve overlaps → redact → export + audit
```

Every detected item is an `Entity` carrying **what** it is and **where** it is (char span
for text; page + bbox for PDF/image). Detectors and redactors are pluggable behind fixed
interfaces, so new modalities (NER, OCR, faces) are additive.

## Slices

### Slice 1 — Detection core ✅ *(spec approved, in progress)*
- **In:** plain text file. **Out:** redacted text + JSON audit log, via CLI.
- `Entity` model + `Span`; `Detector` ABC; `RegexDetector` (email, international phone, IBAN, RIB, credit-card w/ Luhn, national IDs: MA CIN, US SSN, UK NINO, ES DNI/NIE).
- Overlap resolution; `TextRedactor` with 4 styles (labeled, consistent, blackout, remove).
- Audit log with `--redact-audit` hashing option. Stdlib only.
- Spec: `docs/superpowers/specs/2026-08-08-anonymizer-core-slice-design.md`

### Slice 2 — NER + native PDF
- spaCy NER (FR + EN) for PERSON / ORG / LOC → new `NerDetector`, same interface.
- CAMeL-BERT for Arabic names.
- PyMuPDF: extract native PDF text **with coordinates**; extend `Entity` with page + bbox.
- Redact PDFs in place (true black boxes over spans). Adds first third-party deps.

### Slice 3 — OCR + faces
- EasyOCR for scanned pages → text + word boxes feeding the same detectors.
- MediaPipe / OpenCV face detection in scanned IDs and photos → `FaceDetector` emitting box regions.
- `ImageRedactor`: black box / blur / placeholder over regions.

### Slice 4 — Streamlit UI
- Drag-and-drop a file; toggle entity types; choose redaction style; download the clean file.
- Before/after preview. Thin UI layer over the existing library — no core logic in the app.

### Slice 5 — Eval + polish
- Small hand-labeled test set; per-language precision/recall table.
- README with before/after screenshots, supported-entity table, two-command quickstart, demo GIF.
- Sample documents (CV, medical form).

## Cross-cutting principles
- **Everything runs local. Zero API keys.**
- **Library-first**, CLI/UI are thin wrappers.
- **TDD** on the detection/redaction core.
- **Privacy of the tool itself**: the audit log can hash originals; nothing leaves the machine.

## Status
- [x] Slice 1 design spec approved
- [ ] Slice 1 implementation
- [ ] Slice 2 · [ ] Slice 3 · [ ] Slice 4 · [ ] Slice 5
