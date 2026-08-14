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
