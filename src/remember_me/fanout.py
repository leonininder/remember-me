"""Frozen fan-out defaults — single source of truth for System One question sets.

Local candidates first. Jev never ranks. Jev only admits.
"""

from __future__ import annotations

from dataclasses import dataclass

from remember_me.types import (
    Q_ADMIT,
    Q_EMIT_ACTION,
    Q_HYDRATE_ACTION,
    Q_LEAK_RISK,
    Q_NEED_FOR_NEXT_TURN,
    Q_NODE_KIND,
    Q_ON_TOPIC,
    Q_STILL_MATTERS,
    Q_WRITEBACK_ACTION,
)


@dataclass(frozen=True)
class FanOutDefaults:
    """Public defaults for multi-candidate × multi-question batching."""

    batch_candidates: bool = True
    include_raw_query: bool = False  # query_hash only
    optional_network: bool = False
    optional_reflect: bool = False
    core_hydrate_questions: tuple[str, ...] = (
        Q_HYDRATE_ACTION,
        Q_NEED_FOR_NEXT_TURN,
        Q_STILL_MATTERS,
    )
    core_admit_questions: tuple[str, ...] = (Q_ADMIT, Q_NODE_KIND)
    core_emit_questions: tuple[str, ...] = (Q_EMIT_ACTION, Q_LEAK_RISK, Q_ON_TOPIC)
    core_writeback_questions: tuple[str, ...] = (Q_WRITEBACK_ACTION,)


FANOUT_DEFAULTS = FanOutDefaults()
