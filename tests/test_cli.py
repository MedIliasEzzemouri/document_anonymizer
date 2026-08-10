import json

from anonymizer.cli import main


def test_cli_redacts_to_out_file(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("mail a@b.com", encoding="utf-8")
    out = tmp_path / "out.txt"
    audit = tmp_path / "audit.json"

    code = main([str(src), "--style", "labeled",
                 "--out", str(out), "--audit", str(audit)])

    assert code == 0
    assert out.read_text(encoding="utf-8") == "mail [EMAIL]"
    log = json.loads(audit.read_text(encoding="utf-8"))
    assert log["counts"] == {"EMAIL": 1}


def test_cli_types_filter(tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("a@b.com 0612345678", encoding="utf-8")
    out = tmp_path / "out.txt"

    code = main([str(src), "--types", "email", "--out", str(out)])

    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "0612345678" in text
    assert "a@b.com" not in text


def test_cli_ner_flag_runs_without_models(tmp_path, monkeypatch):
    # Force the NER path to use zero engines, so no model download is needed.
    from anonymizer.detectors import ner_engines
    monkeypatch.setattr(ner_engines, "default_engines", lambda: {})

    src = tmp_path / "in.txt"
    src.write_text("mail a@b.com", encoding="utf-8")
    out = tmp_path / "out.txt"

    code = main([str(src), "--ner", "--out", str(out)])

    assert code == 0
    # regex still redacts even with no NER engines available
    assert out.read_text(encoding="utf-8") == "mail [EMAIL]"


def test_cli_prints_to_stdout_when_no_out(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("mail a@b.com", encoding="utf-8")
    code = main([str(src)])
    assert code == 0
    assert "[EMAIL]" in capsys.readouterr().out
