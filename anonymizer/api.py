import json
import os
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from anonymizer import db
from anonymizer.entities import EntityType
from anonymizer.pdf_service import redact_pdf_bytes
from anonymizer.redactors.pdf_redactor import PdfRedactionMode

app = FastAPI(title="Document Anonymizer")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _parse_types(raw: Optional[str]) -> Optional[List[EntityType]]:
    if not raw:
        return None
    return [EntityType[t.strip().upper()] for t in raw.split(",") if t.strip()]
