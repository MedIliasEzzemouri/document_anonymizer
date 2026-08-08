# Document Anonymizer — Slice 1 (Detection Core) Design

**Date:** 2026-08-08
**Status:** Approved
**Scope:** First vertical slice of the Document Anonymizer / PII Redaction Tool.

## Goal

`text file in → regex detection → redacted text + JSON audit log out`, end-to-end, from
the command line, with **zero third-party dependencies** (stdlib only). Establish the
`Entity` data model and the detector/redactor interfaces so later slices (NER, native
PDF, OCR, faces, Streamlit UI) plug in without reworking the core.

## Non-goals (deferred to later slices)

- spaCy / CAMeL-BERT NER (names, orgs, locations) — slice 2
- Native PDF text + coordinates (PyMuPDF) — slice 2
- OCR for scanned pages (EasyOCR) — slice 3
- Face detection in images (MediaPipe/OpenCV) — slice 3
- Streamlit UI — slice 4
- Precision eval + README/demo — slice 5

## Success criteria

- `python -m anonymizer sample.txt --style consistent` prints redacted text and writes an audit log.
- All four redaction styles work: `labeled`, `consistent`, `blackout`, `remove`.
- Regex detectors cover: email, Moroccan + international phone, Moroccan CIN, RIB, IBAN,
  credit card (Luhn-validated).
- Overlapping matches are resolved deterministically (no double-redaction).
- Full unit + end-to-end test coverage; tests pass.

## Module layout

```
document_anonymizer/
├── anonymizer/
│   ├── __init__.py
│   ├── entities.py        # EntityType enum, Span, Entity dataclass
│   ├── pipeline.py        # run detectors → resolve overlaps → redact → audit
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── base.py        # Detector ABC: detect(text) -> list[Entity]
│   │   └── regex_rules.py # RegexDetector + pattern registry
│   ├── redactors/
│   │   ├── __init__.py
│   │   └── text_redactor.py   # 4 styles behind one interface
│   ├── audit.py           # build JSON audit log
│   └── cli.py             # argparse entry point (python -m anonymizer)
├── tests/
├── requirements.txt       # slice 1: empty / stdlib only
└── README.md
```

## Data model (`entities.py`)

```python
class EntityType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    CIN = "CIN"
    RIB = "RIB"
    IBAN = "IBAN"
    CREDIT_CARD = "CREDIT_CARD"
    # PERSON / ORG / LOC reserved for the NER slice

@dataclass(frozen=True)
class Span:
    start: int   # inclusive char offset
    end: int     # exclusive char offset

@dataclass
class Entity:
    type: EntityType
    text: str                 # raw matched value
    span: Span
    detector: str             # provenance: "regex" (later "spacy", "mediapipe")
    score: float = 1.0
    replacement: str | None = None   # filled by the redactor
```

**Extension point:** later slices add image/PDF location (page index + bbox). This will be
introduced then as an optional `region` field; `span` remains the text case. The core
interfaces must not assume text is the only location kind, but we do NOT build `region`
now (YAGNI).

## Detectors

`base.py`:

```python
class Detector(ABC):
    name: str
    @abstractmethod
    def detect(self, text: str) -> list[Entity]: ...
```

`regex_rules.py`: `RegexDetector` driven by a pattern registry mapping `EntityType` →
compiled pattern (+ optional validator, e.g. Luhn for credit cards). `detect()` scans the
text, emits an `Entity` per match with `detector="regex"`.

### Regex pattern set (Morocco-first, Law 09-08 relevant)

| Type | Pattern intent | Validation |
|------|----------------|------------|
| EMAIL | standard local@domain.tld | — |
| PHONE | Moroccan `+212`/`0[5-7]…` + generic international | length/format |
| CIN | Moroccan national ID `[A-Z]{1,2}\d{5,6}` | — |
| RIB | 24-digit Moroccan bank account | length |
| IBAN | `MA` + Moroccan form, plus generic `[A-Z]{2}\d{2}…` | length |
| CREDIT_CARD | 13–19 digit groups | **Luhn check** to cut false positives |

## Pipeline (`pipeline.py`)

1. Run every enabled detector, collect all `Entity` objects.
2. **Resolve overlaps:** sort by `(start, -length)`; greedily keep non-overlapping matches,
   preferring the longer match, then a fixed type-priority order for equal-length ties.
   Discard entities that overlap an already-kept one. This prevents e.g. a phone number
   nested inside a longer digit run from being redacted twice.
3. Hand the clean, sorted entity list to the redactor with the chosen style.
4. Emit `(redacted_text, entities_with_replacements)` and build the audit log.

## Redactor (`redactors/text_redactor.py`)

`TextRedactor(style: RedactionStyle)`; applies replacements **right-to-left** so earlier
char offsets remain valid during mutation.

| Style | Output |
|-------|--------|
| `labeled` | `[EMAIL]` |
| `consistent` | `[EMAIL_1]` — counter keyed on the normalized matched value, so the same value reuses the same token doc-wide |
| `blackout` | `██████` (same length as the original) |
| `remove` | `""` |

Each style sets `entity.replacement` so the audit log can record what each span became.

## Audit log (`audit.py`)

JSON structure:

```json
{
  "source": "sample.txt",
  "timestamp": "2026-08-08T20:00:00Z",
  "style": "consistent",
  "entities": [
    {"type": "EMAIL", "original": "a@b.com", "replacement": "[EMAIL_1]",
     "start": 10, "end": 17, "detector": "regex", "score": 1.0}
  ],
  "counts": {"EMAIL": 2, "PHONE": 1}
}
```

**Privacy callout:** the audit log otherwise stores the *original* PII, which is itself a
leak for a privacy tool. A `--redact-audit` flag stores a SHA-256 hash of the original
instead of the raw value. Default keeps raw (needed for the eval-labeling workflow in
slice 5).

## CLI (`cli.py`, `python -m anonymizer`)

```
python -m anonymizer INPUT.txt \
    [--style labeled|consistent|blackout|remove]   # default: labeled
    [--types email,phone,cin,rib,iban,credit_card] # default: all
    [--out clean.txt]                              # default: stdout
    [--audit log.json]                             # default: none
    [--redact-audit]                               # hash originals in the log
```

The package is **library-first**: `pipeline` / detectors / redactors are importable and
usable without the CLI; `cli.py` is a thin argparse wrapper over them.

## Testing (TDD)

- Per-pattern positive **and** negative tests (e.g. a non-Luhn 16-digit number is NOT a card).
- One test per redaction style, including the `consistent` counter reusing tokens.
- Overlap-resolution test (nested/adjacent matches).
- End-to-end pipeline test on a small sample document with a known expected redaction.
- Audit-log shape test, including `--redact-audit` hashing.
