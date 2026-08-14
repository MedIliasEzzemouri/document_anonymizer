FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Curated runtime deps (excludes camel-tools/PyTorch — container bakes spaCy EN/FR only).
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" python-multipart sqlalchemy psycopg2-binary \
    pymupdf "spacy>=3.7,<3.8"
RUN python -m spacy download en_core_web_sm && python -m spacy download fr_core_news_sm

COPY anonymizer ./anonymizer
COPY static ./static

EXPOSE 8000
CMD ["uvicorn", "anonymizer.api:app", "--host", "0.0.0.0", "--port", "8000"]
