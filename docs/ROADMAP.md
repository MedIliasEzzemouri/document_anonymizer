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

### Slice 2 — NER (Path A: pre-trained) + native PDF
- **Path A — use a pre-trained model** (no training by us): spaCy NER (FR + EN) for
  PERSON / ORG / LOC → new `NerDetector`, same `Entity` interface as the regex detector.
- CAMeL-BERT for Arabic names.
- PyMuPDF: extract native PDF text **with coordinates**; extend `Entity` with page + bbox.
- Redact PDFs in place (true black boxes over spans). Adds first third-party deps.
- Deliverable: name detection working end-to-end — this is the **baseline** to beat later.

### Slice 3 — OCR + faces
- EasyOCR for scanned pages → text + word boxes feeding the same detectors.
- MediaPipe / OpenCV face detection in scanned IDs and photos → `FaceDetector` emitting box regions.
- `ImageRedactor`: black box / blur / placeholder over regions.

### Slice 4 — Dockerized FastAPI + PostgreSQL (browser UI)
- FastAPI service (chosen over Streamlit for speed/testability): `/redact`, `/audit`, `/health`,
  static drag-and-drop UI with PDF.js before/after preview + download.
- **PostgreSQL** stores an **audit trail (metadata only — no documents/PII)**: filename, time,
  mode, per-type counts. GDPR / Law 09-08 relevant.
- Runs via `docker compose up` (api + db containers). Tests use SQLite (offline) via SQLAlchemy.
- Deliberately **not** microservices/gateway (over-engineered for this workload; possible later).
- Spec: `docs/superpowers/specs/2026-08-14-dockerized-api-postgres-design.md`

### Slice 5 — Labeled dataset + eval + polish
- Hand-label a small dataset (names marked per sentence). This same data serves **both**
  evaluation now and fine-tuning in Slice 6.
- Measure the Slice 2 **baseline**: per-language precision/recall table.
- README with before/after screenshots, supported-entity table, two-command quickstart, demo GIF.
- Sample documents (CV, medical form).

### Slice 6 — NER (Path B: train our own)
- **Path B — fine-tune our own model** on the Slice 5 labeled data (spaCy training config
  or transformers fine-tuning), targeting weaknesses of the pre-trained model
  (e.g. Moroccan names it has never seen).
- Compare fine-tuned vs. baseline on the held-out test set; report the improvement.
- Swap the winning model behind the same `NerDetector` interface — no pipeline changes.
- **Depends on:** Slice 2 (baseline) + Slice 5 (labeled data). Cannot start before both.

## Future model expansion (all need PyTorch — currently blocked on install)

A three-model vision beyond the current regex + small-spaCy baseline:

- **Better per-language NER (fits existing `NerDetector` as new engines):** French
  CamemBERT (`Jean-Baptiste/camembert-ner`) / `fr_core_news_lg`; English `en_core_web_trf`
  (RoBERTa) or HF token-classification (BERT/RoBERTa/DeBERTa on CoNLL/OntoNotes); Arabic
  CAMeL; **GLiNER** for zero-shot arbitrary entity types (may reduce need for fine-tuning).
  → a "transformer foundation" slice once torch installs.
- **Document-type classifier (new subsystem):** classify the whole doc (CV / medical / bank /
  legal / invoice…) to drive routing, audit metadata, or per-type PII policies. → its own slice.
  *Open question: what it drives (routing vs metadata vs policy).*
- **Information/PII-type classification (Model 1):** *needs clarification* — may overlap with
  NER typing we already do, or become a sensitivity-level / PII-vs-not false-positive filter.

**Hard prerequisite:** PyTorch install (torch wheel download failed on network). Resolve
before any of the above. See [[ner-baseline-findings]].

### Structured-form detectors (done, on `main`)
- Real test on a Campus France receipt exposed: small spaCy model leaked the ALL-CAPS surname and boxed French labels. Fixes shipped:
  - **DATE** regex detector (birthdates etc.); **REF** type (dossier/case numbers).
  - **LabelDetector**: `Label : Value` extraction (Nom/Prénom/Date de naissance/N° de dossier, FR+EN) — deterministic, 100% precision on forms.
  - **NER noise filter**: drops label/short-token false positives (Nom, Montant, US…).
- Open follow-up: line-aware PDF text reconstruction (preserve newlines) to stop NER over-extending across fields; and CamemBERT (below) for French free-text.

## Cross-cutting principles
- **Everything runs local. Zero API keys.**
- **Library-first**, CLI/UI are thin wrappers.
- **TDD** on the detection/redaction core.
- **Privacy of the tool itself**: the audit log can hash originals; nothing leaves the machine.

## Status
- [x] Slice 1 — detection core (regex, international) merged to `main`, 39 tests passing
- [x] Slice 2a — NER Path A (pre-trained spaCy EN/FR) on text, merged to `main`
- [x] Slice 2b — native PDF read + coordinate-aware redaction (secure/labeled/cover), merged to `main`
  - Finding (fixed): names in **social URLs/handles** (`linkedin.com/in/...`) leaked — added a `URL` regex detector.
  - Open finding: PII **split across a line break** (hyphenated wrap, e.g. an email breaking mid-domain) isn't reconstructed contiguously, so it's missed. Needs dehyphenation in `words_to_text_and_index`. Low frequency.
- [ ] Slice 2c — Arabic NER (CAMeL) — install blocked on PyTorch download; code degrades gracefully
- [ ] Slice 3 — OCR + faces
- [x] Slice 4 — Dockerized FastAPI + PostgreSQL + browser UI, merged to `main` (host port 8010)
- [ ] Slice 5 — labeled dataset + baseline eval + polish
- [ ] Slice 6 — NER Path B (fine-tune our own), compare to baseline
