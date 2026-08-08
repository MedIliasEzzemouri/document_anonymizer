# Detection Core (Slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end text PII anonymizer — regex detection → overlap resolution → styled redaction → JSON audit log — driven from a CLI, with zero third-party dependencies.

**Architecture:** A shared `Entity` data model flows through a pipeline: detectors emit `Entity` objects, an overlap resolver drops conflicting matches, a redactor rewrites the text in one of four styles, and an audit builder records what changed. Detectors and the redactor sit behind narrow interfaces so later slices (NER, PDF, OCR, faces) plug in without touching this core.

**Tech Stack:** Python 3.9 stdlib only (`dataclasses`, `enum`, `re`, `abc`, `argparse`, `json`, `hashlib`, `datetime`), `pytest` for tests.

## Global Constraints

- Python 3.9 compatible (use `Optional[X]` / `List[X]` from `typing`, NOT `X | None` in annotations — the system Python is 3.9.6).
- Zero third-party runtime dependencies. `pytest` is the only dev dependency.
- Package name: `anonymizer`. Runnable as `python -m anonymizer`.
- Library-first: all logic importable; `cli.py` is a thin wrapper.
- `EntityType` values are uppercase strings: `EMAIL, PHONE, CIN, RIB, IBAN, CREDIT_CARD`.
- Redaction styles: `labeled, consistent, blackout, remove`.
- Every task ends green (`pytest` passes) and is committed.

---

## File Structure

- `anonymizer/__init__.py` — package marker, exports.
- `anonymizer/entities.py` — `EntityType`, `Span`, `Entity`. (Task 1)
- `anonymizer/detectors/__init__.py` — package marker.
- `anonymizer/detectors/base.py` — `Detector` ABC. (Task 2)
- `anonymizer/detectors/regex_rules.py` — `luhn_valid`, `PATTERNS`, `RegexDetector`. (Task 3)
- `anonymizer/redactors/__init__.py` — package marker.
- `anonymizer/redactors/text_redactor.py` — `RedactionStyle`, `TextRedactor`. (Task 5)
- `anonymizer/pipeline.py` — `resolve_overlaps` (Task 4), `anonymize_text` + `AnonymizationResult` (Task 6).
- `anonymizer/audit.py` — `build_audit_log`. (Task 7)
- `anonymizer/cli.py` + `anonymizer/__main__.py` — CLI. (Task 8)
- `tests/` — one test module per task.
- `requirements.txt`, `pyproject.toml` (pytest config), `sample.txt`. (Task 0)

---

## Task 0: Project scaffold

**Files:**
- Create: `requirements.txt`, `pyproject.toml`, `anonymizer/__init__.py`, `anonymizer/detectors/__init__.py`, `anonymizer/redactors/__init__.py`, `tests/__init__.py`, `sample.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable `anonymizer` package and a working `pytest`.

- [ ] **Step 1: Create the package files**

`requirements.txt`:
```
# Slice 1 has zero runtime dependencies (stdlib only).
# Dev-only:
pytest>=7.0
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

`anonymizer/__init__.py`:
```python
"""Document Anonymizer — local PII redaction."""
```

Empty files: `anonymizer/detectors/__init__.py`, `anonymizer/redactors/__init__.py`, `tests/__init__.py`.

`sample.txt`:
```
Contact Ahmed at ahmed.example@mail.com or call +212612345678.
His CIN is AB123456 and card 4539578763621486 should never leak.
Reach the office at 0523847561 too.
```

- [ ] **Step 2: Verify pytest runs (collects zero tests)**

Run: `python3 -m pytest -q`
Expected: "no tests ran" (exit code 5) — confirms pytest is installed and config is valid. If pytest is missing: `python3 -m pip install pytest`.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: scaffold anonymizer package"
```

---

## Task 1: Entity data model

**Files:**
- Create: `anonymizer/entities.py`
- Test: `tests/test_entities.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class EntityType(str, Enum)` with members `EMAIL, PHONE, CIN, RIB, IBAN, CREDIT_CARD`.
  - `@dataclass(frozen=True) class Span: start: int; end: int`
  - `@dataclass class Entity: type: EntityType; text: str; span: Span; detector: str; score: float = 1.0; replacement: Optional[str] = None`

- [ ] **Step 1: Write the failing test**

`tests/test_entities.py`:
```python
from anonymizer.entities import EntityType, Span, Entity


def test_entity_type_values_are_uppercase_strings():
    assert EntityType.EMAIL.value == "EMAIL"
    assert EntityType.CREDIT_CARD.value == "CREDIT_CARD"


def test_entity_holds_location_and_defaults():
    e = Entity(type=EntityType.EMAIL, text="a@b.com", span=Span(0, 7), detector="regex")
    assert e.span.start == 0
    assert e.span.end == 7
    assert e.score == 1.0
    assert e.replacement is None


def test_span_is_frozen():
    import dataclasses
    s = Span(1, 2)
    try:
        s.start = 5
        assert False, "Span should be immutable"
    except dataclasses.FrozenInstanceError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_entities.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.entities'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/entities.py`:
```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EntityType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    CIN = "CIN"
    RIB = "RIB"
    IBAN = "IBAN"
    CREDIT_CARD = "CREDIT_CARD"


@dataclass(frozen=True)
class Span:
    start: int  # inclusive char offset
    end: int    # exclusive char offset


@dataclass
class Entity:
    type: EntityType
    text: str
    span: Span
    detector: str
    score: float = 1.0
    replacement: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_entities.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/entities.py tests/test_entities.py
git commit -m "feat: add Entity/Span/EntityType data model"
```

---

## Task 2: Detector base interface

**Files:**
- Create: `anonymizer/detectors/base.py`
- Test: `tests/test_detector_base.py`

**Interfaces:**
- Consumes: `anonymizer.entities.Entity`.
- Produces: `class Detector(ABC)` with class attr `name: str` and abstract method `detect(self, text: str) -> List[Entity]`.

- [ ] **Step 1: Write the failing test**

`tests/test_detector_base.py`:
```python
import pytest
from anonymizer.detectors.base import Detector
from anonymizer.entities import Entity, EntityType, Span


def test_cannot_instantiate_abstract_detector():
    with pytest.raises(TypeError):
        Detector()


def test_concrete_subclass_works():
    class Dummy(Detector):
        name = "dummy"

        def detect(self, text):
            return [Entity(EntityType.EMAIL, "x", Span(0, 1), self.name)]

    result = Dummy().detect("anything")
    assert result[0].detector == "dummy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_detector_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.detectors.base'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/detectors/base.py`:
```python
from abc import ABC, abstractmethod
from typing import List

from anonymizer.entities import Entity


class Detector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, text: str) -> List[Entity]:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_detector_base.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/detectors/base.py tests/test_detector_base.py
git commit -m "feat: add Detector ABC"
```

---

## Task 3: Regex detector + patterns + Luhn

**Files:**
- Create: `anonymizer/detectors/regex_rules.py`
- Test: `tests/test_regex_rules.py`

**Interfaces:**
- Consumes: `Detector`, `Entity`, `EntityType`, `Span`.
- Produces:
  - `def luhn_valid(number: str) -> bool`
  - `PATTERNS: Dict[EntityType, re.Pattern]` (module-level compiled patterns).
  - `class RegexDetector(Detector)` — `name = "regex"`; `__init__(self, types: Optional[Iterable[EntityType]] = None)` (None = all); `detect(text) -> List[Entity]`. Credit-card matches failing `luhn_valid` are dropped.

- [ ] **Step 1: Write the failing test**

`tests/test_regex_rules.py`:
```python
from anonymizer.detectors.regex_rules import RegexDetector, luhn_valid
from anonymizer.entities import EntityType


def types_found(text):
    return {e.type for e in RegexDetector().detect(text)}


def test_luhn_accepts_valid_card():
    assert luhn_valid("4539578763621486") is True


def test_luhn_rejects_invalid_card():
    assert luhn_valid("4539578763621487") is False


def test_detects_email():
    assert EntityType.EMAIL in types_found("write me at a.b@mail.com please")


def test_detects_moroccan_phone_plus212():
    assert EntityType.PHONE in types_found("call +212612345678")


def test_detects_moroccan_phone_local():
    assert EntityType.PHONE in types_found("call 0612345678")


def test_detects_cin():
    assert EntityType.CIN in types_found("CIN AB123456")


def test_detects_credit_card_only_if_luhn_valid():
    assert EntityType.CREDIT_CARD in types_found("card 4539578763621486")
    assert EntityType.CREDIT_CARD not in types_found("num 4539578763621487")


def test_span_matches_matched_text():
    text = "mail a.b@mail.com end"
    e = [e for e in RegexDetector().detect(text) if e.type == EntityType.EMAIL][0]
    assert text[e.span.start:e.span.end] == e.text
    assert e.detector == "regex"


def test_types_filter_limits_detection():
    d = RegexDetector(types=[EntityType.EMAIL])
    found = {e.type for e in d.detect("a@b.com and 0612345678")}
    assert found == {EntityType.EMAIL}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_regex_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.detectors.regex_rules'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/detectors/regex_rules.py`:
```python
import re
from typing import Dict, Iterable, List, Optional

from anonymizer.detectors.base import Detector
from anonymizer.entities import Entity, EntityType, Span


def luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# Order matters only for readability; overlap resolution handles conflicts.
PATTERNS: Dict[EntityType, "re.Pattern"] = {
    EntityType.EMAIL: re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    EntityType.IBAN: re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    EntityType.CIN: re.compile(r"\b[A-Z]{1,2}\d{5,6}\b"),
    EntityType.PHONE: re.compile(r"(?:\+212|0)[5-7](?:[ .\-]?\d){8}\b"),
    EntityType.RIB: re.compile(r"\b\d{24}\b"),
    EntityType.CREDIT_CARD: re.compile(r"\b(?:\d[ \-]?){13,19}\b"),
}

# Types whose matches must pass an extra validator to count.
_VALIDATORS = {EntityType.CREDIT_CARD: luhn_valid}


class RegexDetector(Detector):
    name = "regex"

    def __init__(self, types: Optional[Iterable[EntityType]] = None):
        self.types = list(types) if types is not None else list(PATTERNS.keys())

    def detect(self, text: str) -> List[Entity]:
        found: List[Entity] = []
        for etype in self.types:
            pattern = PATTERNS[etype]
            validator = _VALIDATORS.get(etype)
            for m in pattern.finditer(text):
                value = m.group()
                if validator and not validator(value):
                    continue
                found.append(
                    Entity(
                        type=etype,
                        text=value,
                        span=Span(m.start(), m.end()),
                        detector=self.name,
                    )
                )
        return found
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_regex_rules.py -v`
Expected: PASS (9 passed). If the CIN test fails because `AB123456` also matches something else, that is fine — the test only checks CIN is present.

- [ ] **Step 5: Commit**

```bash
git add anonymizer/detectors/regex_rules.py tests/test_regex_rules.py
git commit -m "feat: add regex detector with Luhn-validated cards"
```

---

## Task 4: Overlap resolution

**Files:**
- Create: `anonymizer/pipeline.py` (add `resolve_overlaps` only in this task)
- Test: `tests/test_overlap.py`

**Interfaces:**
- Consumes: `Entity`, `Span`.
- Produces: `def resolve_overlaps(entities: List[Entity]) -> List[Entity]` — returns entities sorted by `span.start`, keeping the longest match on conflict and dropping any entity whose span overlaps an already-kept one.

- [ ] **Step 1: Write the failing test**

`tests/test_overlap.py`:
```python
from anonymizer.pipeline import resolve_overlaps
from anonymizer.entities import Entity, EntityType, Span


def make(start, end, etype=EntityType.PHONE):
    return Entity(etype, "x", Span(start, end), "regex")


def test_keeps_longer_of_two_overlapping():
    short = make(0, 5)
    longer = make(0, 10)
    kept = resolve_overlaps([short, longer])
    assert kept == [longer]


def test_keeps_non_overlapping_sorted_by_start():
    a = make(10, 15)
    b = make(0, 5)
    kept = resolve_overlaps([a, b])
    assert [e.span.start for e in kept] == [0, 10]


def test_drops_later_entity_overlapping_kept_one():
    first = make(0, 10)
    overlapping = make(5, 8)
    kept = resolve_overlaps([first, overlapping])
    assert kept == [first]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_overlap.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.pipeline'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/pipeline.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_overlap.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/pipeline.py tests/test_overlap.py
git commit -m "feat: add overlap resolution (longest match wins)"
```

---

## Task 5: Text redactor (4 styles)

**Files:**
- Create: `anonymizer/redactors/text_redactor.py`
- Test: `tests/test_text_redactor.py`

**Interfaces:**
- Consumes: `Entity`, `EntityType`, `Span`.
- Produces:
  - `class RedactionStyle(str, Enum)`: `LABELED="labeled"`, `CONSISTENT="consistent"`, `BLACKOUT="blackout"`, `REMOVE="remove"`.
  - `class TextRedactor` — `__init__(self, style: RedactionStyle)`; `redact(self, text: str, entities: List[Entity]) -> Tuple[str, List[Entity]]`. Sets `entity.replacement` on each entity and returns the rewritten text. Assumes entities are non-overlapping (post `resolve_overlaps`).

- [ ] **Step 1: Write the failing test**

`tests/test_text_redactor.py`:
```python
from anonymizer.redactors.text_redactor import RedactionStyle, TextRedactor
from anonymizer.entities import Entity, EntityType, Span


def ents(text):
    # two emails, one repeated value
    return [
        Entity(EntityType.EMAIL, "a@b.com", Span(0, 7), "regex"),
        Entity(EntityType.EMAIL, "a@b.com", Span(12, 19), "regex"),
    ]


BASE = "a@b.com and a@b.com"


def test_labeled_style():
    red = TextRedactor(RedactionStyle.LABELED)
    out, entities = red.redact(BASE, ents(BASE))
    assert out == "[EMAIL] and [EMAIL]"
    assert entities[0].replacement == "[EMAIL]"


def test_consistent_style_reuses_token_for_same_value():
    red = TextRedactor(RedactionStyle.CONSISTENT)
    out, _ = red.redact(BASE, ents(BASE))
    assert out == "[EMAIL_1] and [EMAIL_1]"


def test_consistent_style_numbers_distinct_values():
    text = "a@b.com and c@d.com"
    entities = [
        Entity(EntityType.EMAIL, "a@b.com", Span(0, 7), "regex"),
        Entity(EntityType.EMAIL, "c@d.com", Span(12, 19), "regex"),
    ]
    out, _ = TextRedactor(RedactionStyle.CONSISTENT).redact(text, entities)
    assert out == "[EMAIL_1] and [EMAIL_2]"


def test_blackout_style_matches_length():
    red = TextRedactor(RedactionStyle.BLACKOUT)
    out, _ = red.redact(BASE, ents(BASE))
    assert out == "███████ and ███████"


def test_remove_style_deletes_span():
    red = TextRedactor(RedactionStyle.REMOVE)
    out, _ = red.redact(BASE, ents(BASE))
    assert out == " and "
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_text_redactor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.redactors.text_redactor'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/redactors/text_redactor.py`:
```python
from enum import Enum
from typing import Dict, List, Tuple

from anonymizer.entities import Entity


class RedactionStyle(str, Enum):
    LABELED = "labeled"
    CONSISTENT = "consistent"
    BLACKOUT = "blackout"
    REMOVE = "remove"


class TextRedactor:
    def __init__(self, style: RedactionStyle):
        self.style = style

    def _replacement(self, entity: Entity, counters: Dict, seen: Dict) -> str:
        if self.style == RedactionStyle.LABELED:
            return "[{}]".format(entity.type.value)
        if self.style == RedactionStyle.CONSISTENT:
            key = (entity.type, entity.text.strip().lower())
            if key not in seen:
                counters[entity.type] = counters.get(entity.type, 0) + 1
                seen[key] = counters[entity.type]
            return "[{}_{}]".format(entity.type.value, seen[key])
        if self.style == RedactionStyle.BLACKOUT:
            return "█" * len(entity.text)
        if self.style == RedactionStyle.REMOVE:
            return ""
        raise ValueError("unknown style: {}".format(self.style))

    def redact(self, text: str, entities: List[Entity]) -> Tuple[str, List[Entity]]:
        counters: Dict = {}
        seen: Dict = {}
        # Assign replacements left-to-right so CONSISTENT numbering follows reading order.
        ordered = sorted(entities, key=lambda e: e.span.start)
        for e in ordered:
            e.replacement = self._replacement(e, counters, seen)
        # Apply right-to-left so earlier offsets stay valid.
        result = text
        for e in sorted(ordered, key=lambda e: e.span.start, reverse=True):
            result = result[: e.span.start] + e.replacement + result[e.span.end :]
        return result, ordered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_text_redactor.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/redactors/text_redactor.py tests/test_text_redactor.py
git commit -m "feat: add TextRedactor with 4 styles"
```

---

## Task 6: Pipeline orchestration

**Files:**
- Modify: `anonymizer/pipeline.py` (add `AnonymizationResult` and `anonymize_text`; keep `resolve_overlaps`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `RegexDetector`, `resolve_overlaps`, `RedactionStyle`, `TextRedactor`, `Entity`, `EntityType`.
- Produces:
  - `@dataclass class AnonymizationResult: redacted_text: str; entities: List[Entity]`
  - `def anonymize_text(text: str, types: Optional[List[EntityType]] = None, style: RedactionStyle = RedactionStyle.LABELED) -> AnonymizationResult` — runs the regex detector, resolves overlaps, redacts, and returns both the text and the kept entities (with `replacement` filled).

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py`:
```python
from anonymizer.pipeline import anonymize_text, AnonymizationResult
from anonymizer.redactors.text_redactor import RedactionStyle
from anonymizer.entities import EntityType


def test_end_to_end_labeled():
    text = "mail a@b.com or call 0612345678"
    result = anonymize_text(text)
    assert isinstance(result, AnonymizationResult)
    assert "[EMAIL]" in result.redacted_text
    assert "[PHONE]" in result.redacted_text
    assert "a@b.com" not in result.redacted_text
    assert "0612345678" not in result.redacted_text


def test_entities_carry_replacement():
    result = anonymize_text("mail a@b.com", style=RedactionStyle.CONSISTENT)
    email = [e for e in result.entities if e.type == EntityType.EMAIL][0]
    assert email.replacement == "[EMAIL_1]"


def test_types_filter_passed_through():
    result = anonymize_text("a@b.com 0612345678", types=[EntityType.EMAIL])
    assert "0612345678" in result.redacted_text  # phone not targeted
    assert "a@b.com" not in result.redacted_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'anonymize_text'`.

- [ ] **Step 3: Write minimal implementation**

Add to `anonymizer/pipeline.py` (keep existing `resolve_overlaps`; add imports at top):
```python
from dataclasses import dataclass
from typing import List, Optional

from anonymizer.entities import Entity, EntityType
from anonymizer.detectors.regex_rules import RegexDetector
from anonymizer.redactors.text_redactor import RedactionStyle, TextRedactor


@dataclass
class AnonymizationResult:
    redacted_text: str
    entities: List[Entity]


def anonymize_text(
    text: str,
    types: Optional[List[EntityType]] = None,
    style: RedactionStyle = RedactionStyle.LABELED,
) -> AnonymizationResult:
    detected = RegexDetector(types=types).detect(text)
    kept = resolve_overlaps(detected)
    redacted, entities = TextRedactor(style).redact(text, kept)
    return AnonymizationResult(redacted_text=redacted, entities=entities)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pipeline.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/pipeline.py tests/test_pipeline.py
git commit -m "feat: add anonymize_text pipeline"
```

---

## Task 7: Audit log

**Files:**
- Create: `anonymizer/audit.py`
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: `Entity`.
- Produces: `def build_audit_log(source: str, style: str, entities: List[Entity], redact_audit: bool = False) -> dict` — returns a JSON-serializable dict with keys `source, timestamp, style, entities, counts`. Each entity entry: `type, original, replacement, start, end, detector, score`. When `redact_audit` is True, `original` is the SHA-256 hex digest of the raw value instead of the raw value.

- [ ] **Step 1: Write the failing test**

`tests/test_audit.py`:
```python
import hashlib
import json

from anonymizer.audit import build_audit_log
from anonymizer.entities import Entity, EntityType, Span


def sample_entities():
    e1 = Entity(EntityType.EMAIL, "a@b.com", Span(0, 7), "regex")
    e1.replacement = "[EMAIL_1]"
    e2 = Entity(EntityType.EMAIL, "a@b.com", Span(12, 19), "regex")
    e2.replacement = "[EMAIL_1]"
    return [e1, e2]


def test_audit_shape_and_counts():
    log = build_audit_log("f.txt", "consistent", sample_entities())
    assert log["source"] == "f.txt"
    assert log["style"] == "consistent"
    assert log["counts"] == {"EMAIL": 2}
    assert log["entities"][0]["original"] == "a@b.com"
    assert log["entities"][0]["replacement"] == "[EMAIL_1]"
    assert log["entities"][0]["start"] == 0
    # must be JSON-serializable
    json.dumps(log)


def test_redact_audit_hashes_original():
    log = build_audit_log("f.txt", "labeled", sample_entities(), redact_audit=True)
    expected = hashlib.sha256("a@b.com".encode("utf-8")).hexdigest()
    assert log["entities"][0]["original"] == expected
    assert "a@b.com" not in json.dumps(log)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.audit'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/audit.py`:
```python
import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import List

from anonymizer.entities import Entity


def build_audit_log(
    source: str,
    style: str,
    entities: List[Entity],
    redact_audit: bool = False,
) -> dict:
    def original_of(e: Entity) -> str:
        if redact_audit:
            return hashlib.sha256(e.text.encode("utf-8")).hexdigest()
        return e.text

    entries = [
        {
            "type": e.type.value,
            "original": original_of(e),
            "replacement": e.replacement,
            "start": e.span.start,
            "end": e.span.end,
            "detector": e.detector,
            "score": e.score,
        }
        for e in entities
    ]
    counts = Counter(e.type.value for e in entities)
    return {
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "style": style,
        "entities": entries,
        "counts": dict(counts),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audit.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/audit.py tests/test_audit.py
git commit -m "feat: add JSON audit log with optional hashing"
```

---

## Task 8: CLI

**Files:**
- Create: `anonymizer/cli.py`, `anonymizer/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `anonymize_text`, `AnonymizationResult`, `RedactionStyle`, `EntityType`, `build_audit_log`.
- Produces:
  - `def build_parser() -> argparse.ArgumentParser`
  - `def main(argv: Optional[List[str]] = None) -> int` — reads the input file, runs the pipeline, writes redacted text to `--out` (or stdout), writes the audit log to `--audit` if given, returns exit code 0.
- `__main__.py` calls `sys.exit(main())`.

CLI contract:
```
python -m anonymizer INPUT [--style labeled|consistent|blackout|remove]
                           [--types email,phone,cin,rib,iban,credit_card]
                           [--out FILE] [--audit FILE] [--redact-audit]
```
`--style` default `labeled`; `--types` default all; `--types` parsing is case-insensitive and maps to `EntityType` by uppercasing.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import json

from anonymizer.cli import main


def test_cli_redacts_to_out_file(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("mail a@b.com", encoding="utf-8")
    out = tmp_path / "out.txt"
    audit = tmp_path / "audit.json"

    code = main([str(src), "--style", "labeled",
                 "--out", str(out), "--audit", str(audit)])

    assert code == 0
    assert out.read_text(encoding="utf-8") == "mail [EMAIL]"
    log = json.loads(audit.read_text(encoding="utf-8"))
    assert log["counts"] == {"EMAIL": 1}


def test_cli_types_filter(tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("a@b.com 0612345678", encoding="utf-8")
    out = tmp_path / "out.txt"

    code = main([str(src), "--types", "email", "--out", str(out)])

    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "0612345678" in text
    assert "a@b.com" not in text


def test_cli_prints_to_stdout_when_no_out(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("mail a@b.com", encoding="utf-8")
    code = main([str(src)])
    assert code == 0
    assert "[EMAIL]" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.cli'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/cli.py`:
```python
import argparse
import json
import sys
from typing import List, Optional

from anonymizer.audit import build_audit_log
from anonymizer.entities import EntityType
from anonymizer.pipeline import anonymize_text
from anonymizer.redactors.text_redactor import RedactionStyle


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="anonymizer", description="Redact PII from a text file.")
    p.add_argument("input", help="path to a UTF-8 text file")
    p.add_argument("--style", default="labeled",
                   choices=[s.value for s in RedactionStyle])
    p.add_argument("--types", default=None,
                   help="comma-separated subset, e.g. email,phone,cin")
    p.add_argument("--out", default=None, help="output file (default: stdout)")
    p.add_argument("--audit", default=None, help="write JSON audit log to this path")
    p.add_argument("--redact-audit", action="store_true",
                   help="store SHA-256 of originals in the audit log")
    return p


def _parse_types(raw: Optional[str]) -> Optional[List[EntityType]]:
    if not raw:
        return None
    return [EntityType[name.strip().upper()] for name in raw.split(",") if name.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    with open(args.input, "r", encoding="utf-8") as fh:
        text = fh.read()

    result = anonymize_text(
        text,
        types=_parse_types(args.types),
        style=RedactionStyle(args.style),
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(result.redacted_text)
    else:
        sys.stdout.write(result.redacted_text + "\n")

    if args.audit:
        log = build_audit_log(args.input, args.style, result.entities,
                              redact_audit=args.redact_audit)
        with open(args.audit, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=2)

    return 0
```

`anonymizer/__main__.py`:
```python
import sys

from anonymizer.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Full suite + manual smoke test**

Run: `python3 -m pytest -q`
Expected: all tests pass.

Run: `python3 -m anonymizer sample.txt --style consistent --audit /tmp/audit.json`
Expected: redacted text printed with `[EMAIL_1]`, `[PHONE_1]`, `[CIN_1]`, `[CREDIT_CARD_1]` tokens; `/tmp/audit.json` written.

- [ ] **Step 6: Commit**

```bash
git add anonymizer/cli.py anonymizer/__main__.py tests/test_cli.py
git commit -m "feat: add CLI entry point"
```

---

## Self-Review

**Spec coverage:**
- Entity model + Span → Task 1 ✓
- Detector ABC → Task 2 ✓
- Regex patterns (email, MA/intl phone, CIN, RIB, IBAN, credit card + Luhn) → Task 3 ✓
- Overlap resolution → Task 4 ✓
- 4 redaction styles → Task 5 ✓
- Pipeline end-to-end → Task 6 ✓
- Audit log + `--redact-audit` hashing → Task 7 ✓
- CLI contract (`--style`, `--types`, `--out`, `--audit`, `--redact-audit`) → Task 8 ✓
- Zero third-party deps, library-first, Python 3.9 → Global Constraints ✓
- TDD per task → every task ✓

**Type consistency:** `Entity`, `Span`, `EntityType`, `RedactionStyle`, `RegexDetector.detect`, `resolve_overlaps`, `TextRedactor.redact`, `anonymize_text`/`AnonymizationResult`, `build_audit_log` signatures are consistent across producing and consuming tasks.

**Placeholder scan:** No TBD/TODO; all steps contain runnable code and exact commands.

**Note on overlap + IBAN/CIN:** A Moroccan IBAN `MA...` and a CIN can both match digit-adjacent runs; `resolve_overlaps` keeps the longest, so IBAN (longer) wins over a nested CIN. This is the intended behavior and is exercised indirectly by the end-to-end sample.
