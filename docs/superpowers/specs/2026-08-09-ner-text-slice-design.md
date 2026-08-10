# Slice 2a — Name Detection on Text (Pre-trained NER) Design

**Date:** 2026-08-09
**Status:** Approved
**Scope:** Add multilingual name/entity detection on plain text using pre-trained models
(Path A). Plugs into the existing detection pipeline from Slice 1.

## Goal

Detect `PERSON`, `ORG`, and `LOC` entities in text using pre-trained NER models —
spaCy for English and French, CAMeL Tools for Arabic — and merge them with the existing
regex detections so redaction and audit logging work exactly as they do today. This is the
**Path A baseline** the fine-tuned model (Slice 6) will later be measured against.

## Non-goals (later slices)

- PDF read + coordinate-aware redaction → Slice 2b
- OCR, faces → Slice 3
- Streamlit UI → Slice 4
- Labeled eval set + baseline precision/recall → Slice 5
- Fine-tuning our own NER (Path B) → Slice 6

## Success criteria

- `NerDetector` implements the existing `Detector` interface and emits `Entity` objects with
  correct `PERSON`/`ORG`/`LOC` types, exact character spans, and engine provenance.
- Running all three engines (EN, FR, AR) over a document merges cleanly with regex results;
  overlap resolution dedupes identical spans.
- `--ner` CLI flag turns name detection on; the default fast path (regex only) is unchanged.
- Unit tests run offline with fake engines (no model downloads). One optional slow
  integration test exercises the real spaCy EN model when installed.

## Key decisions

- **Run all models on everything, then merge** (no language detection, no `--lang`). Handles
  mixed FR+AR documents with zero configuration. Accepted trade-off: slower, and a model may
  occasionally guess at foreign-language text (cross-language false positives). Overlap
  resolution + `--types` filtering keep this manageable.
- **NER off by default, opt-in via `--ner`.** Loading three models is slow; the instant
  regex-only path stays the default.
- **Engines are injected, not imported by the detector.** This is what keeps unit tests fast
  and offline and lets Slice 6 swap a fine-tuned model behind the same interface.

## New / changed files

- `anonymizer/entities.py` — add `PERSON`, `ORG`, `LOC` to `EntityType`. (modify)
- `anonymizer/detectors/ner_detector.py` — `NerEngine` type, `LABEL_MAP`, `NerDetector`. (create)
- `anonymizer/detectors/ner_engines.py` — lazy real-engine builders + `default_engines()`. (create)
- `anonymizer/pipeline.py` — `anonymize_text` accepts an optional `detectors` list. (modify)
- `anonymizer/cli.py` — add `--ner` flag. (modify)
- `tests/test_ner_detector.py` — unit tests with fake engines. (create)
- `tests/test_ner_pipeline.py` — NER + regex merge through the pipeline. (create)
- `tests/test_ner_integration.py` — optional slow test on real spaCy EN. (create)
- `requirements.txt`, `README`/spec — dependencies + one-time model setup. (modify)

## Data model change

```python
class EntityType(str, Enum):
    # ... existing structured types ...
    PERSON = "PERSON"
    ORG = "ORG"
    LOC = "LOC"
```

## `NerDetector` (`detectors/ner_detector.py`)

```python
from typing import Callable, Dict, List, Tuple

# An engine takes text and returns (label, start_char, end_char) tuples.
NerEngine = Callable[[str], List[Tuple[str, int, int]]]

# Normalize each library's label vocabulary to our three types.
LABEL_MAP = {
    "PERSON": EntityType.PERSON, "PER": EntityType.PERSON,
    "ORG": EntityType.ORG, "ORGANIZATION": EntityType.ORG,
    "LOC": EntityType.LOC, "LOCATION": EntityType.LOC, "GPE": EntityType.LOC,
}

class NerDetector(Detector):
    name = "ner"
    def __init__(self, engines: Dict[str, NerEngine]):
        self.engines = engines           # e.g. {"spacy-en": fn, "spacy-fr": fn, "camel-ar": fn}
    def detect(self, text: str) -> List[Entity]:
        found = []
        for engine_name, engine in self.engines.items():
            for label, start, end in engine(text):
                etype = LABEL_MAP.get(label.upper())
                if etype is None:
                    continue
                found.append(Entity(etype, text[start:end], Span(start, end), engine_name))
        return found
```

Provenance (`Entity.detector`) is the engine key (`"spacy-en"`, `"spacy-fr"`, `"camel-ar"`),
so Slice 6 can compare engines directly.

## Real engines (`detectors/ner_engines.py`)

Built lazily so importing the package never loads heavy libraries.

- `spacy_engine(model_name)` → loads the model once, returns a closure that yields
  `(ent.label_, ent.start_char, ent.end_char)` for each entity. spaCy provides exact char
  offsets, so this maps directly onto `Span`.
- `camel_engine()` → wraps CAMeL's `NERecognizer`. **CAMeL is token-based (BIO tags), not
  char-based**, so the wrapper must align predicted tokens back to their character offsets in
  the original text (walk the text, match each token, contiguous B-/I- spans of the same type
  become one entity). This is the main engineering effort in the slice.
- `default_engines()` → returns `{"spacy-en": ..., "spacy-fr": ..., "camel-ar": ...}`, skipping
  any engine whose model/library is not installed (so a partial install still runs).

## Pipeline integration (`pipeline.py`)

```python
def anonymize_text(text, types=None, style=RedactionStyle.LABELED, detectors=None):
    if detectors is None:
        detectors = [RegexDetector(types=types)]
    found = []
    for d in detectors:
        found.extend(d.detect(text))
    kept = resolve_overlaps(found)
    ...
```

`types` filtering for NER happens after detection (drop entities whose type isn't requested),
keeping the single `--types` mechanism uniform across detectors.

A helper `build_detectors(types, use_ner)` returns `[RegexDetector(types)]` or
`[RegexDetector(types), NerDetector(default_engines())]`.

## CLI (`cli.py`)

Add `--ner` (store_true, default False). When set, the CLI builds detectors via
`build_detectors(types, use_ner=True)`. All other flags unchanged.

## Dependencies & one-time setup

`requirements.txt` adds:
```
spacy>=3.7
camel-tools
```
(`camel-tools` pulls in `torch` and `transformers`.) One-time model downloads, documented
in the README:
```
python -m spacy download en_core_web_sm
python -m spacy download fr_core_news_sm
camel_data -i ner-arabic          # CAMeL NER model
```
Everything still runs locally with no API keys.

## Error handling

- If a model/library is missing, `default_engines()` omits that engine rather than crashing;
  a one-line warning notes which languages are unavailable.
- `NerDetector` with an empty engine set returns `[]` (regex still runs), so `--ner` on a
  machine with no models degrades gracefully instead of erroring.

## Testing

**Unit (offline, fake engines):**
- Label mapping: `PER`/`PERSON` → PERSON, `GPE`/`LOC` → LOC, unknown label dropped.
- Correct span + provenance from a fake engine.
- Multiple engines merge; identical spans from two engines dedupe via `resolve_overlaps`.
- `--types` filtering removes unrequested NER types.
- Pipeline: regex + fake-NER detections merge and redact together.

**Integration (optional, `@pytest.mark.slow`, skipif model absent):**
- Real spaCy `en_core_web_sm` finds a known name in a sample sentence with a correct span.
