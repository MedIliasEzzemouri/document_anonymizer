# Dockerized FastAPI + PostgreSQL (Slice 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A browser-usable FastAPI service that redacts an uploaded PDF and records an audit trail in PostgreSQL, deployable with `docker compose up`.

**Architecture:** Thin FastAPI layer over the existing anonymizer library. Persistence goes through SQLAlchemy so the same code runs on SQLite (tests, offline) and PostgreSQL (Docker). A static HTML+JS page (served by FastAPI) provides drag-and-drop upload, options, before/after preview, and download.

**Tech Stack:** FastAPI, uvicorn, SQLAlchemy, PostgreSQL (Docker) / SQLite (tests), PyMuPDF, Docker Compose. `pytest` + `TestClient` (`httpx`) for tests.

## Global Constraints

- Persistence stores **audit metadata only** — never document bytes or PII values.
- `db.py` reads `DATABASE_URL` (default `sqlite:///./anonymizer.db`); Docker sets a `postgresql://` URL. Same code both ways.
- API layer is thin; all redaction logic stays in the library (`PdfRedactor`, `detect_entities`).
- Python 3.9-compatible typing in library code; the container image uses `python:3.11-slim`.
- Tests run **without Docker** (SQLite + `TestClient`) and must pass via `.venv/bin/python -m pytest`.
- `fitz` imported lazily; integration tests marked `@pytest.mark.slow` where they build real PDFs.
- Every task ends green and is committed.

## Dependencies to install in the venv (Task 1)
`fastapi`, `uvicorn[standard]`, `python-multipart`, `sqlalchemy`, `httpx` (TestClient), `psycopg2-binary` (Docker runtime only). Command: `.venv/bin/python -m pip install fastapi "uvicorn[standard]" python-multipart sqlalchemy httpx psycopg2-binary`.

---

## File Structure

- `anonymizer/pdf_service.py` — `redact_pdf_bytes(...)`. (Task 1)
- `anonymizer/db.py` — SQLAlchemy `jobs` table + `init_db`/`record_job`/`list_jobs`. (Task 2)
- `anonymizer/api.py` — FastAPI `app`: `/health`, `/redact`, `/audit`, `/`. (Tasks 3–5)
- `static/index.html` — UI. (Task 6)
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`. (Task 7)
- `requirements.txt` — add web + db deps. (Task 1)
- `tests/test_pdf_service.py`, `tests/test_db.py`, `tests/test_api.py`.

---

## Task 1: pdf_service.redact_pdf_bytes + dependencies

**Files:**
- Create: `anonymizer/pdf_service.py`
- Modify: `requirements.txt`
- Test: `tests/test_pdf_service.py`

**Interfaces:**
- Consumes: `PdfRedactor`, `PdfRedactionMode`.
- Produces: `redact_pdf_bytes(data: bytes, mode: PdfRedactionMode = PdfRedactionMode.SECURE, types=None, use_ner: bool = False) -> Tuple[bytes, dict]` — temp-file round trip; returns `(output_pdf_bytes, audit_dict)`.

- [ ] **Step 1: Install deps and record them**

Run: `.venv/bin/python -m pip install fastapi "uvicorn[standard]" python-multipart sqlalchemy httpx psycopg2-binary`

Append to `requirements.txt`:
```
# Slice 4 — web API + audit DB
fastapi
uvicorn[standard]
python-multipart
sqlalchemy
psycopg2-binary   # PostgreSQL driver (Docker runtime)
httpx             # dev: FastAPI TestClient
```

- [ ] **Step 2: Write the failing test**

`tests/test_pdf_service.py`:
```python
import pytest

fitz = pytest.importorskip("fitz")


def _pdf_bytes(body):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), body, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.mark.slow
def test_redact_pdf_bytes_removes_email():
    from anonymizer.pdf_service import redact_pdf_bytes
    from anonymizer.redactors.pdf_redactor import PdfRedactionMode

    data = _pdf_bytes("Email a@b.com here")
    out_bytes, audit = redact_pdf_bytes(data, mode=PdfRedactionMode.SECURE)

    reopened = fitz.open(stream=out_bytes, filetype="pdf")
    text = "".join(p.get_text() for p in reopened)
    reopened.close()
    assert "a@b.com" not in text
    assert audit["counts"].get("EMAIL", 0) >= 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pdf_service.py -v -m slow`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.pdf_service'`.

- [ ] **Step 4: Write minimal implementation**

`anonymizer/pdf_service.py`:
```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_pdf_service.py -v -m slow`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add anonymizer/pdf_service.py tests/test_pdf_service.py requirements.txt
git commit -m "feat: redact_pdf_bytes service helper + web/db deps"
```

---

## Task 2: db.py — audit persistence

**Files:**
- Create: `anonymizer/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `DATABASE_URL` env.
- Produces:
  - `init_db() -> None` (creates the `jobs` table).
  - `record_job(filename: str, mode: str, ner: bool, counts: dict) -> int` (returns new id; `total_entities` = sum of counts).
  - `list_jobs(limit: int = 20) -> List[dict]` (newest first; `created_at` as ISO string).

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:
```python
def test_record_and_list_job(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}".format(tmp_path / "t.db"))
    from anonymizer import db

    db.init_db()
    jid = db.record_job("cv.pdf", "secure", True, {"EMAIL": 2, "PERSON": 1})
    assert isinstance(jid, int)

    jobs = db.list_jobs()
    assert jobs[0]["filename"] == "cv.pdf"
    assert jobs[0]["mode"] == "secure"
    assert jobs[0]["ner"] is True
    assert jobs[0]["counts"] == {"EMAIL": 2, "PERSON": 1}
    assert jobs[0]["total_entities"] == 3
    assert isinstance(jobs[0]["created_at"], str)  # JSON-serializable


def test_list_jobs_newest_first(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}".format(tmp_path / "t2.db"))
    from anonymizer import db

    db.init_db()
    db.record_job("a.pdf", "secure", False, {"EMAIL": 1})
    db.record_job("b.pdf", "secure", False, {"PHONE": 1})
    jobs = db.list_jobs()
    assert jobs[0]["filename"] == "b.pdf"  # newest first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.db'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/db.py`:
```python
import os
from datetime import datetime, timezone
from typing import List

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Integer, MetaData, String, Table,
    create_engine, insert, select,
)

_DEFAULT_URL = "sqlite:///./anonymizer.db"
metadata = MetaData()

jobs = Table(
    "jobs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("filename", String, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("mode", String, nullable=False),
    Column("ner", Boolean, nullable=False),
    Column("counts", JSON, nullable=False),
    Column("total_entities", Integer, nullable=False),
)


def _engine():
    return create_engine(os.environ.get("DATABASE_URL", _DEFAULT_URL), future=True)


def init_db() -> None:
    metadata.create_all(_engine())


def record_job(filename: str, mode: str, ner: bool, counts: dict) -> int:
    total = sum(counts.values())
    with _engine().begin() as conn:
        result = conn.execute(insert(jobs).values(
            filename=filename, created_at=datetime.now(timezone.utc),
            mode=mode, ner=ner, counts=counts, total_entities=total,
        ))
        return int(result.inserted_primary_key[0])


def list_jobs(limit: int = 20) -> List[dict]:
    with _engine().connect() as conn:
        rows = conn.execute(
            select(jobs).order_by(jobs.c.id.desc()).limit(limit)
        ).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        created = d["created_at"]
        d["created_at"] = created.isoformat() if hasattr(created, "isoformat") else str(created)
        out.append(d)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add anonymizer/db.py tests/test_db.py
git commit -m "feat: postgres/sqlite audit persistence (jobs table)"
```

---

## Task 3: FastAPI app + /health

**Files:**
- Create: `anonymizer/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `db.init_db`.
- Produces: `app` (FastAPI); `GET /health -> {"status": "ok"}`; runs `init_db()` on startup.

- [ ] **Step 1: Write the failing test**

`tests/test_api.py`:
```python
def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///{}".format(tmp_path / "api.db"))
    from fastapi.testclient import TestClient
    from anonymizer.api import app
    return TestClient(app)


def test_health(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_health -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anonymizer.api'`.

- [ ] **Step 3: Write minimal implementation**

`anonymizer/api.py`:
```python
import json
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_health -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add anonymizer/api.py tests/test_api.py
git commit -m "feat: FastAPI app with /health + startup init_db"
```

---

## Task 4: POST /redact

**Files:**
- Modify: `anonymizer/api.py`
- Test: `tests/test_api.py` (add test)

**Interfaces:**
- Consumes: `redact_pdf_bytes`, `db.record_job`, `_parse_types`, `PdfRedactionMode`.
- Produces: `POST /redact` (multipart `file`, `mode`, `ner`, `types`) → PDF response + `X-Redaction-Counts` header; records a job. Non-PDF → 400.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:
```python
import json
import pytest

fitz = pytest.importorskip("fitz")


def _pdf(body):
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), body, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.mark.slow
def test_redact_returns_clean_pdf_and_records_job(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        files = {"file": ("cv.pdf", _pdf("Email a@b.com here"), "application/pdf")}
        r = client.post("/redact", files=files, data={"mode": "secure"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert b"a@b.com" not in r.content or True  # bytes may be compressed; verify via reopen
        reopened = fitz.open(stream=r.content, filetype="pdf")
        text = "".join(p.get_text() for p in reopened)
        reopened.close()
        assert "a@b.com" not in text
        counts = json.loads(r.headers["x-redaction-counts"])
        assert counts.get("EMAIL", 0) >= 1

        audit = client.get("/audit").json()
        assert audit[0]["filename"] == "cv.pdf"
        assert audit[0]["total_entities"] >= 1


def test_redact_rejects_non_pdf(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        files = {"file": ("note.txt", b"hello", "text/plain")}
        r = client.post("/redact", files=files, data={"mode": "secure"})
        assert r.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py -v -m slow`
Expected: FAIL — 404/405 (no `/redact` route yet).

- [ ] **Step 3: Write minimal implementation**

Append to `anonymizer/api.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api.py -v -m slow`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add anonymizer/api.py tests/test_api.py
git commit -m "feat: POST /redact endpoint + audit recording"
```

---

## Task 5: GET /audit and GET / (serve UI)

**Files:**
- Modify: `anonymizer/api.py`
- Test: `tests/test_api.py` (add test)

**Interfaces:**
- Consumes: `db.list_jobs`.
- Produces: `GET /audit` → JSON list; `GET /` → serves `static/index.html` (FileResponse; if missing, a minimal HTML string so the route never 500s).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:
```python
def test_audit_empty_then_listed(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        assert client.get("/audit").json() == []


def test_root_serves_html(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_audit_empty_then_listed tests/test_api.py::test_root_serves_html -v`
Expected: FAIL — 404 on `/audit` and `/`.

- [ ] **Step 3: Write minimal implementation**

Append to `anonymizer/api.py`:
```python
import os

_STATIC_INDEX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "index.html")


@app.get("/audit")
def audit() -> list:
    return db.list_jobs()


@app.get("/")
def index():
    if os.path.exists(_STATIC_INDEX):
        return FileResponse(_STATIC_INDEX, media_type="text/html")
    return Response("<h1>Document Anonymizer</h1><p>UI not found.</p>",
                    media_type="text/html")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api.py -v -m "not slow"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add anonymizer/api.py tests/test_api.py
git commit -m "feat: /audit list + serve static UI at /"
```

---

## Task 6: static/index.html (browser UI)

**Files:**
- Create: `static/index.html`

**Interfaces:**
- Consumes: `POST /redact`, `GET /audit` endpoints.
- Produces: the drag-and-drop UI (no automated test; verified by launch in Task 7).

- [ ] **Step 1: Write the UI**

`static/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Document Anonymizer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<style>
  body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0f1420;color:#e7ecf3}
  header{padding:18px 24px;background:#151c2c;border-bottom:1px solid #24304a}
  main{display:flex;gap:24px;padding:24px;flex-wrap:wrap}
  .panel{background:#151c2c;border:1px solid #24304a;border-radius:10px;padding:16px}
  #drop{flex:1;min-width:280px;border:2px dashed #3a4a6a;text-align:center;padding:40px;border-radius:10px;cursor:pointer}
  #drop.hover{background:#1b2740}
  label{display:block;margin:8px 0 4px} .row{margin:6px 0}
  button{background:#3b82f6;color:#fff;border:0;padding:10px 16px;border-radius:8px;cursor:pointer;font-size:15px}
  button:disabled{opacity:.5}
  canvas{max-width:100%;border:1px solid #24304a;border-radius:6px;margin-top:8px}
  .warn{color:#f59e0b} .muted{color:#8ea0bd;font-size:13px}
  code{background:#0b1020;padding:1px 5px;border-radius:4px}
</style>
</head>
<body>
<header><h2>🛡 Document Anonymizer</h2><span class="muted">Drop a PDF, get a redacted copy. Runs local.</span></header>
<main>
  <section class="panel" style="min-width:240px">
    <label>Redaction mode</label>
    <div class="row"><label><input type="radio" name="mode" value="secure" checked> secure (removes text)</label></div>
    <div class="row"><label><input type="radio" name="mode" value="labeled"> labeled</label></div>
    <div class="row"><label><input type="radio" name="mode" value="cover"> cover <span class="warn">(insecure)</span></label></div>
    <label><input type="checkbox" id="ner"> Detect names (NER)</label>
    <label>Redact types <span class="muted">(blank = all)</span></label>
    <div id="types" class="row muted">
      <label><input type="checkbox" value="EMAIL" checked>EMAIL</label>
      <label><input type="checkbox" value="PHONE" checked>PHONE</label>
      <label><input type="checkbox" value="PERSON" checked>PERSON</label>
      <label><input type="checkbox" value="LOC" checked>LOC</label>
      <label><input type="checkbox" value="URL" checked>URL</label>
      <label><input type="checkbox" value="IBAN" checked>IBAN</label>
      <label><input type="checkbox" value="CREDIT_CARD" checked>CARD</label>
      <label><input type="checkbox" value="CIN" checked>CIN</label>
      <label><input type="checkbox" value="SSN" checked>SSN</label>
      <label><input type="checkbox" value="NINO" checked>NINO</label>
      <label><input type="checkbox" value="DNI" checked>DNI</label>
    </div>
  </section>

  <section class="panel" style="flex:1;min-width:320px">
    <div id="drop">Drop a PDF here or click to choose<input type="file" id="file" accept="application/pdf" hidden></div>
    <div class="row"><button id="go" disabled>Redact</button> <span id="status" class="muted"></span></div>
    <div id="summary" class="row"></div>
    <div style="display:flex;gap:16px;flex-wrap:wrap">
      <div><b>Before</b><canvas id="before"></canvas></div>
      <div><b>After</b><canvas id="after"></canvas></div>
    </div>
    <div class="row"><a id="dl" style="display:none"><button>⬇ Download redacted PDF</button></a></div>
  </section>
</main>
<script>
const $=s=>document.querySelector(s);
let picked=null, outBlob=null;
const drop=$("#drop"), fileInput=$("#file");
drop.onclick=()=>fileInput.click();
drop.ondragover=e=>{e.preventDefault();drop.classList.add("hover")};
drop.ondragleave=()=>drop.classList.remove("hover");
drop.ondrop=e=>{e.preventDefault();drop.classList.remove("hover");pick(e.dataTransfer.files[0])};
fileInput.onchange=e=>pick(e.target.files[0]);
function pick(f){ if(!f) return; picked=f; $("#go").disabled=false; drop.textContent=f.name; render(f,"#before"); }

async function render(src,sel){
  const buf = src instanceof Blob ? await src.arrayBuffer() : src;
  const pdf = await pdfjsLib.getDocument({data:buf}).promise;
  const page = await pdf.getPage(1);
  const vp = page.getViewport({scale:1.1});
  const c=$(sel); c.width=vp.width; c.height=vp.height;
  await page.render({canvasContext:c.getContext("2d"),viewport:vp}).promise;
}

$("#go").onclick=async()=>{
  if(!picked) return;
  const mode=document.querySelector('input[name=mode]:checked').value;
  const ner=$("#ner").checked;
  const types=[...document.querySelectorAll('#types input:checked')].map(x=>x.value).join(",");
  const fd=new FormData(); fd.append("file",picked); fd.append("mode",mode);
  fd.append("ner",ner); fd.append("types",types);
  $("#status").textContent="Redacting…"; $("#go").disabled=true;
  const r=await fetch("/redact",{method:"POST",body:fd});
  if(!r.ok){ $("#status").textContent="Error: "+r.status; $("#go").disabled=false; return; }
  const counts=JSON.parse(r.headers.get("X-Redaction-Counts")||"{}");
  outBlob=await r.blob();
  $("#summary").innerHTML="Removed: "+Object.entries(counts).map(([k,v])=>`<code>${k} ${v}</code>`).join(" ")||"nothing";
  await render(outBlob,"#after");
  const a=$("#dl"); a.href=URL.createObjectURL(outBlob); a.download=picked.name.replace(/\.pdf$/i,"_redacted.pdf");
  a.style.display="inline-block";
  $("#status").textContent=mode==="cover"?"⚠ cover mode: text NOT truly removed":"Done.";
  $("#go").disabled=false;
};
</script>
</body>
</html>
```

- [ ] **Step 2: Sanity check it is served**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_root_serves_html -v`
Expected: PASS (now serves the real file).

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: browser UI (drag-drop, options, PDF.js preview, download)"
```

---

## Task 7: Docker (Dockerfile + compose) + smoke test

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

**Interfaces:**
- Consumes: everything above.
- Produces: a running `api` + `db` stack via `docker compose up`.

- [ ] **Step 1: Write the Docker files**

`.dockerignore`:
```
.venv
venv
Pdf_test
__pycache__
*.pyc
.git
.pytest_cache
*.db
docs
```

`Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm && python -m spacy download fr_core_news_sm
COPY anonymizer ./anonymizer
COPY static ./static
EXPOSE 8000
CMD ["uvicorn", "anonymizer.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

`docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: anon
      POSTGRES_PASSWORD: anon
      POSTGRES_DB: anonymizer
    volumes:
      - pgdata:/var/lib/postgresql/data
  api:
    build: .
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://anon:anon@db:5432/anonymizer
    ports:
      - "8000:8000"
volumes:
  pgdata:
```

- [ ] **Step 2: Build and start the stack**

Run: `docker compose up --build -d`
Expected: both containers start. (First build downloads spaCy models — may take a few minutes.)

- [ ] **Step 3: Smoke test the running service**

Run: `sleep 5 && curl -s localhost:8000/health`
Expected: `{"status":"ok"}`.

Run:
```bash
curl -s -o /tmp/red.pdf -D - -F "file=@Pdf_test/01_cv_en_sarah_mitchell.pdf" -F "mode=secure" localhost:8000/redact | grep -i x-redaction-counts
curl -s localhost:8000/audit
```
Expected: a counts header, `/tmp/red.pdf` written, and `/audit` lists the job (persisted in Postgres).

- [ ] **Step 4: Tear down**

Run: `docker compose down`
Expected: stack stops (volume `pgdata` persists).

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: Dockerfile + docker-compose (api + postgres)"
```

---

## Self-Review

**Spec coverage:**
- `redact_pdf_bytes` service → Task 1 ✓
- Postgres/SQLite audit persistence (jobs, metadata only) → Task 2 ✓
- `/health` + startup init → Task 3 ✓
- `POST /redact` + counts header + job recording + non-PDF 400 → Task 4 ✓
- `/audit` + serve UI at `/` → Task 5 ✓
- Static drag-drop UI + PDF.js preview + download + cover warning → Task 6 ✓
- Dockerfile (bakes spaCy EN/FR) + compose (api + db) + smoke → Task 7 ✓
- Tests run offline on SQLite via TestClient → Tasks 2–5 ✓
- Audit metadata only, no PII in DB → Task 2 schema (no bytes/values) ✓

**Type consistency:** `redact_pdf_bytes(data, mode, types, use_ner) -> (bytes, dict)`, `init_db()/record_job(filename, mode, ner, counts) -> int/list_jobs(limit) -> List[dict]`, `PdfRedactionMode`, `_parse_types`, and the `X-Redaction-Counts` header are consistent across Tasks 1–7. `DATABASE_URL` is the single config point used by `db._engine()` and the compose file.

**Placeholder scan:** No TBD/TODO; all code steps contain runnable code.
