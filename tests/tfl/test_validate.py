"""CandidateFact schema + value_struct closed validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from remember_me.tfl.ontology import Ontology, default_ontology_path
from remember_me.tfl.types import CandidateFact
from remember_me.tfl.validate import validate_candidate, validate_value_struct_caps


@pytest.fixture
def ont() -> Ontology:
    return Ontology.load(default_ontology_path())


def _base(**kwargs):
    data = {
        "entity": "user",
        "attribute": "weather",
        "qualifier": "local",
        "value_struct": {"condition": "sunny"},
        "observed_at": datetime(2026, 9, 22, 9, 0, tzinfo=UTC),
        "source_event_id": "evt_1",
        "extract_method": "deterministic",
    }
    data.update(kwargs)
    return data


def test_accept_weather(ont: Ontology):
    res = validate_candidate(_base(), ontology=ont)
    assert res.ok
    assert res.fact_key == "user.weather.local"
    assert res.candidate is not None


def test_reject_unknown_properties():
    with pytest.raises(ValidationError):
        CandidateFact.model_validate({**_base(), "extra_field": "nope"})


def test_reject_sole_prose_key(ont: Ontology):
    res = validate_candidate(_base(value_struct={"text": "long diary"}), ontology=ont)
    assert not res.ok
    assert res.quarantine
    assert "sole" in res.reason or "forbidden" in res.reason


def test_reject_bad_ontology_enum(ont: Ontology):
    res = validate_candidate(
        _base(value_struct={"condition": "hurricane"}),
        ontology=ont,
    )
    assert not res.ok
    assert res.quarantine


def test_reject_depth(ont: Ontology):
    deep = {"a": {"b": {"c": {"d": 1}}}}
    assert validate_value_struct_caps(deep) is not None
    res = validate_candidate(_base(value_struct=deep), ontology=ont)
    assert not res.ok


def test_reject_oversize_bytes(ont: Ontology):
    # force bytes over 2048 with many keys
    blob = {f"k{i}": "a" * 50 for i in range(50)}
    err = validate_value_struct_caps(blob)
    assert err is not None
    res = validate_candidate(
        _base(attribute="insects", qualifier="play", value_struct={"stance": "x"}),
        ontology=ont,
    )
    assert res.ok  # control
    res2 = validate_candidate(
        {
            **_base(attribute="insects", qualifier="play"),
            "value_struct": blob,
        },
        ontology=ont,
    )
    assert not res2.ok


def test_unknown_entity_quarantine(ont: Ontology):
    res = validate_candidate(_base(entity="stranger"), ontology=ont)
    assert not res.ok
    assert res.quarantine
    assert res.fact_key and res.fact_key.startswith("quarantine.")
