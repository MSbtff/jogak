import io
import json

from jogak.cli import main

from .conftest import FIXTURES

LAW = str(FIXTURES / "law.txt")


def test_cli_plain(capsys):
    assert main([LAW, "--max-size", "80"]) == 0
    out = capsys.readouterr().out
    assert "── #0 [-]" in out
    assert "[제2장 보안 조직 > 제4조(정보보호책임자)]" in out


def test_cli_json(capsys):
    assert main([LAW, "--max-size", "10000", "--no-merge", "--json", "--title", "규정"]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(rows) == 11
    assert rows[1]["path"] == ["규정", "제1장 총칙"]


def test_cli_tree(capsys):
    assert main([LAW, "--tree"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "제1장 총칙"
    assert out[1].startswith("  제1조(목적)  이 규정은")


def test_cli_stdin(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("제1조(목적) 본문이다."))
    assert main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["text"] == "제1조(목적) 본문이다."
