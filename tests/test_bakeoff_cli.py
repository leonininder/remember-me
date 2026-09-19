"""Bake-off offline + CLI smoke."""

from __future__ import annotations

import json
from pathlib import Path

from remember_me.bakeoff import load_queries, run_bakeoff
from remember_me.cli import main

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "personal_prefs"


def test_fixtures_have_50_queries():
    cases = load_queries(FIXTURES / "queries.json")
    assert len(cases) == 50


def test_bakeoff_writes_metrics(tmp_path: Path):
    out = tmp_path / "metrics.json"
    report = run_bakeoff(fixtures_dir=FIXTURES, out_path=out, k=5)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["n_queries"] == 50
    assert "baseline" in data
    assert "jev_gated" in data
    assert data["jev_gated"]["jev_calls"] > 0
    assert "precision_at_k" in data["baseline"]
    assert report["jev_gated"]["n_queries"] == 50


def test_cli_demo(capsys):
    assert main(["demo"]) == 0
    captured = capsys.readouterr()
    assert "Jev called: True" in captured.out


def test_cli_bakeoff(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # bakeoff loads fixtures from package-relative path
    out = tmp_path / "bakeoff_metrics.json"
    rc = main(["bakeoff", "--out", str(out), "--k", "5"])
    assert rc == 0
    assert out.exists()


def test_cli_score_report_missing(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["score-report", "--scorecard", "missing.md"]) == 1
