# Slice 4 — Dockerized FastAPI + PostgreSQL Audit DB Design

**Date:** 2026-08-14
**Status:** Approved
**Scope:** A browser-usable service: upload a PDF, get a redacted copy back, with an audit
trail stored in PostgreSQL — all running in Docker via docker-compose. Thin API over the
existing anonymizer library.

## Goal

Let a user redact a PDF from the browser (no terminal per file) through a FastAPI service,
persisting an audit record (metadata only) per job in PostgreSQL, with the whole thing
deployable via `docker compose up`.

## Non-goals (explicitly out)

- Microservices / API gateway (deliberately deferred — over-engineered for this workload; a
  later distributed-systems exercise if desired).
- Storing documents or PII values in the DB — **only audit metadata is persisted**.
- Arabic NER in the container (CAMeL needs PyTorch, still blocked). Container bakes spaCy
  EN/FR small models only.
- Auth / multi-user / rate limiting (later, if the gateway slice happens).

## Success criteria

- `docker compose up` starts `api` + `db`; `http://localhost:8000` serves the UI.
- Uploading a PDF returns a redacted PDF with PII removed; a job row is written to Postgres.
- `GET /audit` lists recent jobs (metadata only).
- The full test suite runs **without Docker** (SQLite in-memory) and passes.

## Architecture

```
browser (static/index.html)  --HTTP-->  api (FastAPI)  -->  pdf_service.redact_pdf_bytes
                                              |                    -> PdfRedactor (library)
                                              v
                                         db (PostgreSQL)  -- jobs table (audit metadata)
```

The anonymizer library is unchanged. `api.py` is a thin transport layer. `db.py` abstracts
persistence behind SQLAlchemy so tests use SQLite and Docker uses Postgres with identical code.

## Files

- `anonymizer/pdf_service.py` — `redact_pdf_bytes(data, mode, types, use_ner) -> (bytes, dict)`.
- `anonymizer/db.py` — SQLAlchemy engine from `DATABASE_URL`; `jobs` table; `init_db()`,
  `record_job(...)`, `list_jobs(limit=20)`.
- `anonymizer/api.py` — FastAPI `app` with `/health`, `/redact`, `/audit`, `/`.
- `static/index.html` — drag-and-drop UI, options, PDF.js before/after preview, download.
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`.
- `requirements.txt` += `fastapi`, `uvicorn[standard]`, `python-multipart`, `sqlalchemy`, `psycopg2-binary`.
- `tests/test_pdf_service.py`, `tests/test_db.py`, `tests/test_api.py`.

## Database (audit trail — metadata only)

`jobs` table:

| column | type | note |
|--------|------|------|
| id | integer PK autoincrement | |
| filename | text | original upload name |
| created_at | datetime (UTC) | |
| mode | text | secure / labeled / cover |
| ner | boolean | was name detection on |
| counts | JSON | per-type counts, e.g. `{"EMAIL":2,"PERSON":4}` |
| total_entities | integer | sum of counts |

**No document bytes, no PII values.** This is the GDPR / Law 09-08 audit record: proof of
*what kind* of data was removed and when, without retaining the sensitive data itself.

`db.py`:
```python
def init_db() -> None                      # create tables if absent
def record_job(filename, mode, ner, counts) -> int   # returns new job id
def list_jobs(limit: int = 20) -> List[dict]         # newest first
```
Engine built from `DATABASE_URL` env (default `sqlite:///./anonymizer.db`; Docker sets a
`postgresql://...` URL). JSON column uses SQLAlchemy's `JSON` type (works on both backends).

## Service layer

`pdf_service.redact_pdf_bytes(data: bytes, mode: PdfRedactionMode, types, use_ner) -> (bytes, dict)`:
writes the bytes to a temp file, runs `PdfRedactor(...).redact(tmp_in, tmp_out)`, reads the
output bytes, returns `(output_bytes, audit_dict)`. No Streamlit/FastAPI import — reusable and
independently testable (integration test with fitz).

## API endpoints (`api.py`)

- `GET /health` → `{"status": "ok"}`.
- `POST /redact` — multipart form: `file` (UploadFile), `mode` (str, default `secure`),
  `ner` (bool, default false), `types` (optional comma-separated). Runs `redact_pdf_bytes`,
  calls `record_job(...)`, returns the PDF via `Response(content=bytes, media_type="application/pdf")`
  with header `X-Redaction-Counts` = JSON counts and `Content-Disposition` attachment.
  Non-PDF upload → HTTP 400.
- `GET /audit` → `list_jobs()` as JSON.
- `GET /` → serves `static/index.html` (FileResponse).

`app` calls `init_db()` on startup.

## Frontend (`static/index.html`)

Self-contained page (vanilla JS + PDF.js from CDN): drag-and-drop a PDF, choose mode / NER /
entity-type checkboxes, POST to `/redact`, read `X-Redaction-Counts` for the summary, render
before/after page previews with PDF.js, and offer download of the returned PDF. `cover` mode
shows a ⚠️ "text not truly removed" warning. A small "recent jobs" panel fetches `/audit`.

## Docker

- `Dockerfile`: `python:3.11-slim` → `pip install -r requirements.txt` → download spaCy models
  (`en_core_web_sm`, `fr_core_news_sm`) → copy source → `CMD ["uvicorn", "anonymizer.api:app",
  "--host", "0.0.0.0", "--port", "8000"]`.
- `docker-compose.yml`:
  - `db`: `postgres:16`, env `POSTGRES_USER/PASSWORD/DB`, named volume `pgdata`.
  - `api`: `build: .`, `depends_on: db`, `environment: DATABASE_URL=postgresql://user:pass@db:5432/anonymizer`,
    `ports: "8000:8000"`.
- `.dockerignore`: `.venv`, `Pdf_test`, `__pycache__`, `.git`, `*.db`.
- **Run:** `docker compose up --build` → `http://localhost:8000`.

## Error handling

- Non-PDF / unreadable upload → 400 with a JSON error message.
- DB unavailable at startup → `init_db()` retries a few times (Postgres may boot slower than
  the api container), then fails loudly.
- `cover` mode still returns a valid (insecure) PDF; the warning is surfaced in the UI.

## Testing

**Offline (no Docker, SQLite in-memory / temp file):**
- `test_db.py`: `record_job` then `list_jobs` returns it, newest first; `counts` JSON round-trips.
- `test_api.py` (`TestClient`, `DATABASE_URL=sqlite://` temp): `/health` ok; `/redact` with a
  built-in-test PDF returns `application/pdf`, the email is absent from the body,
  `X-Redaction-Counts` has EMAIL≥1, and a job row is recorded; `/audit` lists it; a `.txt`
  upload → 400.

**Integration:**
- `test_pdf_service.py` (importorskip fitz): `redact_pdf_bytes` removes the email from output bytes.

**Docker smoke (manual):** `docker compose up --build`, then `curl localhost:8000/health` → ok,
and a `curl -F file=@sample.pdf localhost:8000/redact` round-trip.
