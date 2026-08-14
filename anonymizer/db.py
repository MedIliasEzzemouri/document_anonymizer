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
