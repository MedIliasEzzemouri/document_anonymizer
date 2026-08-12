import pytest

fitz = pytest.importorskip("fitz")


def _make_pdf(path, body):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), body, fontsize=11)
    doc.save(str(path))
    doc.close()


@pytest.mark.slow
def test_secure_mode_removes_pii_from_output(tmp_path):
    from anonymizer.redactors.pdf_redactor import PdfRedactor, PdfRedactionMode

    src = tmp_path / "in.pdf"
    out = tmp_path / "out.pdf"
    _make_pdf(src, "Email a@b.com here")

    audit = PdfRedactor(mode=PdfRedactionMode.SECURE).redact(str(src), str(out))

    reopened = fitz.open(str(out))
    text = "".join(p.get_text() for p in reopened)
    reopened.close()
    assert "a@b.com" not in text                    # truly removed
    assert audit["counts"].get("EMAIL", 0) >= 1
    assert audit["entities"][0]["page"] == 0


@pytest.mark.slow
def test_cover_mode_keeps_text(tmp_path):
    from anonymizer.redactors.pdf_redactor import PdfRedactor, PdfRedactionMode

    src = tmp_path / "in.pdf"
    out = tmp_path / "out.pdf"
    _make_pdf(src, "Email a@b.com here")

    PdfRedactor(mode=PdfRedactionMode.COVER).redact(str(src), str(out))

    reopened = fitz.open(str(out))
    text = "".join(p.get_text() for p in reopened)
    reopened.close()
    assert "a@b.com" in text                          # cover mode leaves text (insecure)
