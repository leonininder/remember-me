"""Persistent GateAuditRecord store — append-only, no secrets/bodies.

David P1 follow-through: structured audit beyond in-memory EscalationRecord.
Default backend is JSONL (one JSON object per line). SQLite optional via path
ending in ``.sqlite`` / ``.db``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from remember_me.redact import assert_no_secrets
from remember_me.types import (
    EmitDecision,
    EscalationRecord,
    GateDecision,
    WritebackDecision,
)

GateName = Literal["hydrate", "emit", "writeback", "escalate", "admit"]

# Positive allowlist for persisted snapshots (David: denylist is a leak surface).
_AUDIT_SNAPSHOT_ALLOWLIST = frozenset(
    {
        "node_id",
        "kind",
        "tags",
        "degree",
        "last_touch",
        "local_score",
        "tokens_est",
        "proposed_chars",
        "proposed_summary_sha256",
        "sink",
        "target",
        "salience",
        "horizon",
        "egress_id",
    }
)


class GateAuditRecord(BaseModel):
    """Append-only audit row for a gate / escalate decision.

    Never carries marker bodies, secrets, free-text summaries, or raw query text.
    """

    record_id: str = Field(default_factory=lambda: uuid4().hex)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_gate: str
    node_id: str = ""
    action: str = ""
    confidence: float = 0.0
    fail_closed: bool = False
    reason: str = ""
    sink_or_target: str = ""
    band: str = ""
    redacted_snapshot: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self.redacted_snapshot = _sanitize_snapshot(self.redacted_snapshot)


def _sanitize_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only positively allowlisted keys; drop secret-like string values."""
    from remember_me.redact import allowlist_snapshot

    if not snapshot:
        return {}
    out = allowlist_snapshot(snapshot, allowed=_AUDIT_SNAPSHOT_ALLOWLIST)
    cleaned: dict[str, Any] = {}
    for k, v in out.items():
        if isinstance(v, str):
            lowered = v.lower()
            if any(
                b in lowered
                for b in ("sk-", "api_key=", "password=", "secret=", "bearer ", "@")
            ):
                continue
            if len(v) > 200:
                v = v[:197] + "..."
        elif isinstance(v, list):
            kept = []
            for item in v:
                if isinstance(item, str):
                    low = item.lower()
                    if any(
                        b in low
                        for b in ("sk-", "api_key=", "password=", "secret=", "bearer ", "@")
                    ):
                        continue
                kept.append(item)
            v = kept
        cleaned[str(k)] = v
    return cleaned


def record_from_hydrate(decision: GateDecision) -> GateAuditRecord:
    snap: dict[str, Any] = {"local_score": decision.local_score}
    if decision.escalation is not None:
        snap.update(decision.escalation.redacted_snapshot)
    return GateAuditRecord(
        source_gate="hydrate",
        node_id=decision.node_id,
        action=str(decision.action.value if hasattr(decision.action, "value") else decision.action),
        confidence=float(decision.confidence),
        fail_closed=bool(decision.fail_closed),
        reason=decision.reason,
        band=decision.escalation.band if decision.escalation else "",
        redacted_snapshot=snap,
    )


def record_from_emit(decision: EmitDecision) -> GateAuditRecord:
    snap: dict[str, Any] = {"proposed_chars": decision.proposed_chars}
    if decision.escalation is not None:
        snap.update(decision.escalation.redacted_snapshot)
    return GateAuditRecord(
        source_gate="emit",
        node_id="",
        action=str(decision.action.value if hasattr(decision.action, "value") else decision.action),
        confidence=float(decision.confidence),
        fail_closed=bool(decision.fail_closed),
        reason=decision.reason,
        sink_or_target=decision.sink,
        band=decision.escalation.band if decision.escalation else "",
        redacted_snapshot=snap,
    )


def record_from_writeback(decision: WritebackDecision) -> GateAuditRecord:
    snap: dict[str, Any] = {}
    if decision.escalation is not None:
        snap.update(decision.escalation.redacted_snapshot)
    return GateAuditRecord(
        source_gate="writeback",
        node_id=decision.node_id,
        action=str(decision.action.value if hasattr(decision.action, "value") else decision.action),
        confidence=float(decision.confidence),
        fail_closed=bool(decision.fail_closed),
        reason=decision.reason,
        sink_or_target=decision.target,
        band=decision.escalation.band if decision.escalation else "",
        redacted_snapshot=snap,
    )


def record_from_escalation(esc: EscalationRecord) -> GateAuditRecord:
    return GateAuditRecord(
        source_gate="escalate",
        node_id=esc.node_id,
        action=esc.proposed_action,
        confidence=float(esc.confidence),
        fail_closed=esc.band == "fail_closed",
        reason=esc.reason,
        sink_or_target=esc.source_gate,
        band=esc.band,
        redacted_snapshot=dict(esc.redacted_snapshot),
    )


class GateAuditStore:
    """Append-only persistent store for ``GateAuditRecord``.

    - path ending in ``.sqlite`` / ``.db`` → SQLite backend
    - otherwise → JSONL backend (default)
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        suffix = self.path.suffix.lower()
        self._backend: Literal["jsonl", "sqlite"] = (
            "sqlite" if suffix in {".sqlite", ".db", ".sqlite3"} else "jsonl"
        )
        if self._backend == "sqlite":
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.touch()

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gate_audit (
                    record_id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    source_gate TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    fail_closed INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    sink_or_target TEXT NOT NULL,
                    band TEXT NOT NULL,
                    redacted_snapshot TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def append(self, record: GateAuditRecord) -> GateAuditRecord:
        """Append one sanitized record. Raises if secrets slip through."""
        # Re-sanitize + pre-flight (defense in depth).
        record = GateAuditRecord.model_validate(record.model_dump())
        assert_no_secrets(
            {
                "action": record.action,
                "reason": record.reason,
                "redacted_snapshot": record.redacted_snapshot,
            }
        )
        payload = record.model_dump(mode="json")
        with self._lock:
            if self._backend == "jsonl":
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
            else:
                with sqlite3.connect(self.path) as conn:
                    conn.execute(
                        """
                        INSERT INTO gate_audit (
                            record_id, ts, source_gate, node_id, action, confidence,
                            fail_closed, reason, sink_or_target, band, redacted_snapshot
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload["record_id"],
                            payload["ts"],
                            payload["source_gate"],
                            payload["node_id"],
                            payload["action"],
                            payload["confidence"],
                            1 if payload["fail_closed"] else 0,
                            payload["reason"],
                            payload["sink_or_target"],
                            payload["band"],
                            json.dumps(payload["redacted_snapshot"], ensure_ascii=False),
                        ),
                    )
                    conn.commit()
        return record

    def read_all(self) -> list[GateAuditRecord]:
        """Read every record in append order."""
        with self._lock:
            if self._backend == "jsonl":
                if not self.path.exists():
                    return []
                out: list[GateAuditRecord] = []
                with self.path.open(encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        out.append(GateAuditRecord.model_validate(json.loads(line)))
                return out
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM gate_audit ORDER BY rowid ASC"
                ).fetchall()
            return [
                GateAuditRecord(
                    record_id=r["record_id"],
                    ts=r["ts"],
                    source_gate=r["source_gate"],
                    node_id=r["node_id"],
                    action=r["action"],
                    confidence=r["confidence"],
                    fail_closed=bool(r["fail_closed"]),
                    reason=r["reason"],
                    sink_or_target=r["sink_or_target"],
                    band=r["band"],
                    redacted_snapshot=json.loads(r["redacted_snapshot"]),
                )
                for r in rows
            ]

    def __len__(self) -> int:
        return len(self.read_all())
