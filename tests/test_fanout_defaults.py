"""Fan-out defaults frozen contract."""

from __future__ import annotations

from remember_me.fanout import FANOUT_DEFAULTS, FanOutDefaults
from remember_me.jev_client import _hydrate_questions
from remember_me.types import (
    Q_HYDRATE_ACTION,
    Q_NEED_FOR_NEXT_TURN,
    Q_NETWORK_ROUTE,
    Q_STILL_MATTERS,
    Q_TRIGGER_REFLECT,
)


def test_fanout_defaults_frozen_values():
    assert FANOUT_DEFAULTS.batch_candidates is True
    assert FANOUT_DEFAULTS.include_raw_query is False
    assert FANOUT_DEFAULTS.optional_network is False
    assert FANOUT_DEFAULTS.optional_reflect is False
    # frozen dataclass
    try:
        FANOUT_DEFAULTS.batch_candidates = False  # type: ignore[misc]
        raise AssertionError("expected frozen")
    except Exception:
        pass


def test_fanout_core_hydrate_question_ids_stable():
    assert FANOUT_DEFAULTS.core_hydrate_questions == (
        Q_HYDRATE_ACTION,
        Q_NEED_FOR_NEXT_TURN,
        Q_STILL_MATTERS,
    )


def test_fanout_optional_network_adds_question():
    base = _hydrate_questions(optional_network=False, optional_reflect=False)
    assert Q_NETWORK_ROUTE not in base
    assert Q_TRIGGER_REFLECT not in base
    expanded = _hydrate_questions(optional_network=True, optional_reflect=True)
    assert Q_NETWORK_ROUTE in expanded
    assert Q_TRIGGER_REFLECT in expanded


def test_fanout_defaults_type():
    assert isinstance(FANOUT_DEFAULTS, FanOutDefaults)
