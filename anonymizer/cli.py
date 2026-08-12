import argparse
import json
import os
import sys
from typing import List, Optional

from anonymizer.audit import build_audit_log
from anonymizer.entities import EntityType
from anonymizer.pipeline import anonymize_text, build_detectors
from anonymizer.redactors.text_redactor import RedactionStyle
from anonymizer.redactors.pdf_redactor import PdfRedactor, PdfRedactionMode


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
    p.add_argument("--ner", action="store_true",
                   help="also run name detection (spaCy/CAMeL); slower, loads models")
    p.add_argument("--pdf-mode", default="secure",
                   choices=[m.value for m in PdfRedactionMode],
                   help="PDF redaction appearance (default: secure)")
    return p


def _default_pdf_out(path: str) -> str:
    stem, _ext = os.path.splitext(path)
    return stem + "_redacted.pdf"


def _parse_types(raw: Optional[str]) -> Optional[List[EntityType]]:
    if not raw:
        return None
    return [EntityType[name.strip().upper()] for name in raw.split(",") if name.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

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

    with open(args.input, "r", encoding="utf-8") as fh:
        text = fh.read()

    parsed_types = _parse_types(args.types)
    result = anonymize_text(
        text,
        types=parsed_types,
        style=RedactionStyle(args.style),
        detectors=build_detectors(types=parsed_types, use_ner=args.ner),
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
