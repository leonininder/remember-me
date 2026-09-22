"""FactKey minting + ontology_v0 fixture tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from remember_me.tfl.ontology import (
    FactKeyMintError,
    Ontology,
    default_ontology_path,
    mint_fact_key,
    normalize_component,
    normalize_fact_key,
)

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = ROOT / "fixtures" / "memorybench_tfl" / "schema" / "ontology_v0.json"


def test_ontology_v0_fixture_matches_plan_stub():
    assert ONTOLOGY_PATH.is_file()
    data = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    assert data["ontology_id"] == "tfl_ontology_v0"
    assert "user" in data["entities"]
    assert "user.weather.local" in data["fact_key_examples"]
    assert data["attributes"]["user"]["weather"]["qualifiers"] == [
        "local",
        "forecast_today",
    ]
    assert default_ontology_path() == ONTOLOGY_PATH


def test_normalize_component_nfkc_and_caps():
    assert normalize_component("  Weather  ") == "weather"
    assert normalize_component("foo--bar!!") == "foo_bar"
    assert len(normalize_component("a" * 100)) == 64


def test_mint_user_domain_keys(ontology: Ontology):
    assert (
        mint_fact_key("user", "weather", "local", ontology=ontology)
        == "user.weather.local"
    )
    assert (
        mint_fact_key("USER", "Insects", "Play", ontology=ontology)
        == "user.insects.play"
    )
    assert mint_fact_key("user", "pref", "theme", ontology=ontology) == "user.pref.theme"


def test_bare_weather_illegal(ontology: Ontology):
    with pytest.raises(FactKeyMintError, match="bare"):
        mint_fact_key("weather", "local", ontology=ontology, allow_quarantine_bucket=False)


def test_unknown_routes_quarantine(ontology: Ontology):
    key = mint_fact_key("user", "unknown_attr", "x", ontology=ontology)
    assert key.startswith("quarantine.")


def test_normalize_fact_key():
    assert normalize_fact_key("User.Weather.Local") == "user.weather.local"


@pytest.fixture
def ontology() -> Ontology:
    return Ontology.load(ONTOLOGY_PATH)
