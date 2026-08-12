import json


def test_pdf_input_routes_to_redactor(tmp_path, monkeypatch):
    import anonymizer.cli as cli

    calls = {}

    class FakeRedactor:
        def __init__(self, mode=None, types=None, use_ner=False):
            calls["mode"] = mode

        def redact(self, in_path, out_path):
            with open(out_path, "w") as fh:
                fh.write("%PDF-fake")
            calls["out"] = out_path
            return {"source": in_path, "mode": "secure",
                    "entities": [], "counts": {"EMAIL": 1}}

    monkeypatch.setattr(cli, "PdfRedactor", FakeRedactor)

    src = tmp_path / "doc.pdf"
    src.write_text("dummy")
    audit = tmp_path / "log.json"

    code = cli.main([str(src), "--pdf-mode", "secure", "--audit", str(audit)])

    assert code == 0
    assert calls["out"].endswith("doc_redacted.pdf")
    assert json.loads(audit.read_text())["counts"] == {"EMAIL": 1}
