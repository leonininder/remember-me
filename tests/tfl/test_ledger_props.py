"""Ledger property tests: no dual-active; supersede valid_to; as_of one belief."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from remember_me.tfl.canonical import value_struct_equal
from remember_me.tfl.ledger import DualActiveError, FactLedger
from remember_me.tfl.types import LEDGER_SCHEMA_VERSION, FactStatus


@pytest.fixture(params=["sqlite", "jsonl"])
def ledger(tmp_path: Path, request: pytest.FixtureRequest) -> FactLedger:
    if request.param == "sqlite":
        return FactLedger(tmp_path / "ledger.sqlite")
    return FactLedger(tmp_path / "ledger.jsonl")


def test_schema_version_field(ledger: FactLedger):
    assert ledger.ledger_schema_version == LEDGER_SCHEMA_VERSION
    fv = ledger.upsert(
        "user.weather.local",
        {"condition": "sunny"},
        source_event_id="e1",
    )
    assert fv.ledger_schema_version == LEDGER_SCHEMA_VERSION


def test_upsert_then_supersede_sets_valid_to(ledger: FactLedger):
    t0 = datetime(2026, 9, 21, 10, 0, 1, tzinfo=UTC)
    t1 = datetime(2026, 9, 22, 9, 0, 2, tzinfo=UTC)
    v0 = ledger.upsert(
        "user.weather.local",
        {"condition": "sunny"},
        receive_ts=t0,
        valid_from=t0,
        source_event_id="day1",
    )
    assert v0.status == FactStatus.ACTIVE
    v1 = ledger.supersede(
        "user.weather.local",
        {"condition": "rainy"},
        receive_ts=t1,
        valid_from=t1,
        source_event_id="day2",
    )
    assert v1.status == FactStatus.ACTIVE
    assert v1.version_id != v0.version_id
    old = ledger.list_versions("user.weather.local")
    by_id = {x.version_id: x for x in old}
    incumbent = by_id[v0.version_id]
    assert incumbent.status == FactStatus.SUPERSEDED
    assert incumbent.valid_to == t1
    assert incumbent.superseded_by == v1.version_id
    ledger.assert_no_dual_active()


def test_as_of_returns_one_belief(ledger: FactLedger):
    t0 = datetime(2026, 9, 21, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 9, 22, 9, 0, 0, tzinfo=UTC)
    ledger.upsert(
        "user.weather.local",
        {"condition": "sunny"},
        receive_ts=t0,
        valid_from=t0,
        source_event_id="d1",
    )
    ledger.supersede(
        "user.weather.local",
        {"condition": "rainy"},
        receive_ts=t1,
        valid_from=t1,
        source_event_id="d2",
    )
    mid = t0 + timedelta(hours=1)
    belief = ledger.as_of("user.weather.local", mid)
    assert belief is not None
    assert belief.value_struct == {"condition": "sunny"}
    now_belief = ledger.as_of("user.weather.local", t1 + timedelta(seconds=1))
    assert now_belief is not None
    assert now_belief.value_struct == {"condition": "rainy"}
    # exactly one active
    actives = [
        v
        for v in ledger.list_versions("user.weather.local")
        if v.status == FactStatus.ACTIVE
    ]
    assert len(actives) == 1


def test_upsert_same_value_no_new_version(ledger: FactLedger):
    v0 = ledger.upsert(
        "user.pref.theme",
        {"theme": "dark"},
        confidence=0.5,
        source_event_id="a",
    )
    v1 = ledger.upsert(
        "user.pref.theme",
        {"theme": "dark"},
        confidence=0.9,
        source_event_id="b",
    )
    assert v0.version_id == v1.version_id
    assert v1.confidence == 0.9
    assert len(ledger.list_versions("user.pref.theme")) == 1


def test_upsert_material_change_supersedes(ledger: FactLedger):
    ledger.upsert("user.home.city", {"city": "Taipei"}, source_event_id="1")
    v2 = ledger.upsert("user.home.city", {"city": "Tainan"}, source_event_id="2")
    assert v2.status == FactStatus.ACTIVE
    versions = ledger.list_versions("user.home.city")
    assert len(versions) == 2
    assert sum(1 for v in versions if v.status == FactStatus.ACTIVE) == 1
    assert sum(1 for v in versions if v.status == FactStatus.SUPERSEDED) == 1


def test_expire_clears_active(ledger: FactLedger):
    ledger.upsert("user.insects.play", {"stance": "fun"}, source_event_id="c")
    expired = ledger.expire("user.insects.play")
    assert expired is not None
    assert expired.status == FactStatus.EXPIRED
    assert expired.valid_to is not None
    assert ledger.get_active("user.insects.play") is None


def test_tombstone(ledger: FactLedger):
    ledger.upsert("user.insects.safety", {"stance": "caution"}, source_event_id="s")
    ts = ledger.tombstone("user.insects.safety")
    assert ts is not None
    assert ts.status == FactStatus.TOMBSTONED
    assert ledger.get_active("user.insects.safety") is None


def test_property_never_dual_active_random_ops(ledger: FactLedger):
    """Property: random upsert/supersede/expire sequences never dual-active."""
    rng = random.Random(42)
    keys = [
        "user.weather.local",
        "user.weather.forecast_today",
        "user.pref.theme",
        "user.home.city",
    ]
    values = [
        {"condition": "sunny"},
        {"condition": "rainy"},
        {"condition": "cloudy"},
        {"theme": "dark"},
        {"theme": "light"},
        {"city": "Taipei"},
        {"city": "Kaohsiung"},
    ]
    t = datetime(2026, 9, 22, 0, 0, tzinfo=UTC)
    for i in range(80):
        t = t + timedelta(seconds=1)
        key = rng.choice(keys)
        op = rng.choice(["upsert", "supersede", "expire", "upsert"])
        val = rng.choice(values)
        if op == "upsert":
            ledger.upsert(key, val, receive_ts=t, valid_from=t, source_event_id=f"e{i}")
        elif op == "supersede":
            ledger.supersede(
                key, val, receive_ts=t, valid_from=t, source_event_id=f"e{i}"
            )
        else:
            ledger.expire(key, at=t)
        ledger.assert_no_dual_active()
        # as_of returns at most one row per key (None or one)
        belief = ledger.as_of(key, t)
        if belief is not None:
            assert belief.fact_key == key


def test_dual_active_detector(tmp_path: Path):
    """Sanity: DualActiveError raised if invariant manually broken (sqlite)."""
    path = tmp_path / "broken.sqlite"
    led = FactLedger(path)
    led.upsert("user.pref.theme", {"theme": "dark"}, source_event_id="1")
    # Manually insert a second active via backend
    import json
    import sqlite3
    from uuid import uuid4

    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO fact_versions (
                version_id, fact_key, value_struct, valid_from, valid_to,
                receive_ts, observed_at, source_event_id, confidence,
                salience_tier, ttl_hint, status, superseded_by,
                conflicts_with, should_forget_incumbent_applied,
                ledger_schema_version
            ) VALUES (?, ?, ?, ?, NULL, ?, NULL, ?, 0, NULL, NULL, 'active', NULL, '[]', 0, ?)
            """,
            (
                uuid4().hex,
                "user.pref.theme",
                json.dumps({"theme": "light"}),
                datetime.now(UTC).isoformat(),
                datetime.now(UTC).isoformat(),
                "evil",
                LEDGER_SCHEMA_VERSION,
            ),
        )
        conn.commit()
    with pytest.raises(DualActiveError):
        led.get_active("user.pref.theme")


def test_value_struct_equal_ignores_key_order():
    assert value_struct_equal({"a": 1, "b": 2}, {"b": 2, "a": 1})
    assert not value_struct_equal({"a": 1}, {"a": 2})
