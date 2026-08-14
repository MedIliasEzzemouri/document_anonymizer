import os
import tempfile
from typing import List, Optional, Tuple

from anonymizer.entities import EntityType
from anonymizer.redactors.pdf_redactor import PdfRedactor, PdfRedactionMode


def redact_pdf_bytes(
    data: bytes,
    mode: PdfRedactionMode = PdfRedactionMode.SECURE,
    types: Optional[List[EntityType]] = None,
    use_ner: bool = False,
) -> Tuple[bytes, dict]:
    tmpdir = tempfile.mkdtemp(prefix="anon_")
    in_path = os.path.join(tmpdir, "in.pdf")
    out_path = os.path.join(tmpdir, "out.pdf")
    with open(in_path, "wb") as fh:
        fh.write(data)
    audit = PdfRedactor(mode=mode, types=types, use_ner=use_ner).redact(in_path, out_path)
    with open(out_path, "rb") as fh:
        out_bytes = fh.read()
    return out_bytes, audit
