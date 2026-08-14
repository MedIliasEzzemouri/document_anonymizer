import json
import os
import time
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

_STATIC_INDEX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "index.html")

from anonymizer import db
from anonymizer.entities import EntityType
from anonymizer.pdf_service import redact_pdf_bytes
from anonymizer.redactors.pdf_redactor import PdfRedactionMode

app = FastAPI(title="Document Anonymizer")


@app.on_event("startup")
def _startup() -> None:
    # Postgres may boot slower than this container; retry a few times before giving up.
    for _ in range(10):
        try:
            db.init_db()
            return
        except Exception:
            time.sleep(2)
    db.init_db()  # final attempt — let the error surface if the DB is truly down


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _parse_types(raw: Optional[str]) -> Optional[List[EntityType]]:
    if not raw:
        return None
    return [EntityType[t.strip().upper()] for t in raw.split(",") if t.strip()]


@app.post("/redact")
async def redact(
    file: UploadFile = File(...),
    mode: str = Form("secure"),
    ner: bool = Form(False),
    types: Optional[str] = Form(None),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf uploads are supported.")
    data = await file.read()
    out_bytes, audit = redact_pdf_bytes(
        data, mode=PdfRedactionMode(mode), types=_parse_types(types), use_ner=ner,
    )
    db.record_job(filename=file.filename, mode=mode, ner=ner, counts=audit["counts"])
    stem = file.filename[:-4]
    return Response(
        content=out_bytes,
        media_type="application/pdf",
        headers={
            "X-Redaction-Counts": json.dumps(audit["counts"]),
            "Content-Disposition": 'attachment; filename="{}_redacted.pdf"'.format(stem),
        },
    )


@app.get("/audit")
def audit() -> list:
    return db.list_jobs()


@app.get("/")
def index():
    if os.path.exists(_STATIC_INDEX):
        return FileResponse(_STATIC_INDEX, media_type="text/html")
    return Response("<h1>Document Anonymizer</h1><p>UI not found.</p>",
                    media_type="text/html")
