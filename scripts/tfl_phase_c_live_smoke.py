#!/usr/bin/env python3
"""Optional Phase C live smoke — redacted logs only.

Refuses if TYPESAFE_API_KEY missing. Never prints the key or raw diary.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        print("REFUSE: TYPESAFE_API_KEY missing — no live smoke")
        return 2

    from remember_me.tfl.ledger import FactLedger
    from remember_me.tfl.quarantine import QuarantineQueue
    from remember_me.tfl.reconcile import HttpJevReconcileGate, ReconcileEngine
    from remember_me.tfl.redact import assert_reconcile_outbound_safe
    from remember_me.tfl.types import CandidateFact

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        ledger = FactLedger(td_path / "smoke.sqlite")
        ledger.upsert(
            "user.weather.local",
            {"condition": "sunny"},
            source_event_id="smoke_d0",
            salience_tier="ephemeral",
        )
        q = QuarantineQueue(bound_n=8, spill_dir=td_path / "spill")
        gate = HttpJevReconcileGate(api_key=key, timeout_s=30.0)
        eng = ReconcileEngine(ledger, gate, quarantine=q)
        cand = CandidateFact(
            entity="user",
            attribute="weather",
            qualifier="local",
            value_struct={"condition": "rainy"},
            observed_at=datetime.now(UTC),
            source_event_id="smoke_phase_c",
            extract_method="deterministic",
            salience_hint="ephemeral",
        )
        result = eng.reconcile_candidate(cand)
        if gate.last_outbound is not None:
            assert_reconcile_outbound_safe(gate.last_outbound)

        out = {
            "ok": True,
            "model_pin": gate.model_pin,
            "action": result.action.value,
            "applied": result.applied,
            "fail_closed": result.fail_closed,
            "reason": result.reason,
            "fact_key": result.fact_key,
            "quarantine_count": q.total_count(),
            "usage": gate.last_usage,
            "response_model": gate.last_response_model,
            "outbound_keys": sorted((gate.last_outbound or {}).keys()),
            "outbound_new_keys": sorted(
                ((gate.last_outbound or {}).get("new") or {}).keys()
            ),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
