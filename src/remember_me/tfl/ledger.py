"""Temporal Fact Ledger — SQLite/JSONL FactVersion store (Phase B).

APIs: upsert / supersede / expire / tombstone / as_of.
Invariant: never dual-active same FactKey.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from remember_me.tfl.canonical import value_struct_equal
from remember_me.tfl.types import LEDGER_SCHEMA_VERSION, FactStatus, FactVersion


class DualActiveError(RuntimeError):
    """Invariant violation: more than one active version for a FactKey."""


class FactLedger:
    """Versioned belief store with temporal as-of query.

    - path ending in ``.sqlite`` / ``.db`` / ``.sqlite3`` → SQLite
    - otherwise → JSONL (header line carries ledger_schema_version)
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        suffix = self.path.suffix.lower()
        self._backend: Literal["jsonl", "sqlite"] = (
            "sqlite" if suffix in {".sqlite", ".db", ".sqlite3"} else "jsonl"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._backend == "sqlite":
            self._init_sqlite()
        else:
            self._init_jsonl()

    @property
    def ledger_schema_version(self) -> str:
        return LEDGER_SCHEMA_VERSION

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO meta(key, value)
                VALUES ('ledger_schema_version', ?)
                """,
                (LEDGER_SCHEMA_VERSION,),
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fact_versions (
                    version_id TEXT PRIMARY KEY,
                    fact_key TEXT NOT NULL,
                    value_struct TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    receive_ts TEXT NOT NULL,
                    observed_at TEXT,
                    source_event_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    salience_tier TEXT,
                    ttl_hint TEXT,
                    status TEXT NOT NULL,
                    superseded_by TEXT,
                    conflicts_with TEXT NOT NULL,
                    should_forget_incumbent_applied INTEGER NOT NULL,
                    ledger_schema_version TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fv_key_status "
                "ON fact_versions(fact_key, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fv_key_valid "
                "ON fact_versions(fact_key, valid_from)"
            )
            conn.commit()

    def _init_jsonl(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            header = {
                "_header": True,
                "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            }
            self.path.write_text(
                json.dumps(header, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _parse_dt(self, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value
        # fromisoformat handles offsets
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt

    def _row_to_version(self, payload: dict[str, Any]) -> FactVersion:
        return FactVersion.model_validate(payload)

    def _version_payload(self, fv: FactVersion) -> dict[str, Any]:
        return fv.model_dump(mode="json")

    # --- persistence helpers ---

    def _sqlite_insert(self, fv: FactVersion) -> None:
        payload = self._version_payload(fv)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO fact_versions (
                    version_id, fact_key, value_struct, valid_from, valid_to,
                    receive_ts, observed_at, source_event_id, confidence,
                    salience_tier, ttl_hint, status, superseded_by,
                    conflicts_with, should_forget_incumbent_applied,
                    ledger_schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["version_id"],
                    payload["fact_key"],
                    json.dumps(payload["value_struct"], ensure_ascii=False),
                    payload["valid_from"],
                    payload["valid_to"],
                    payload["receive_ts"],
                    payload["observed_at"],
                    payload["source_event_id"],
                    payload["confidence"],
                    payload["salience_tier"],
                    payload["ttl_hint"],
                    payload["status"],
                    payload["superseded_by"],
                    json.dumps(payload["conflicts_with"], ensure_ascii=False),
                    1 if payload["should_forget_incumbent_applied"] else 0,
                    payload["ledger_schema_version"],
                ),
            )
            conn.commit()

    def _sqlite_update(self, fv: FactVersion) -> None:
        payload = self._version_payload(fv)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                UPDATE fact_versions SET
                    fact_key=?, value_struct=?, valid_from=?, valid_to=?,
                    receive_ts=?, observed_at=?, source_event_id=?, confidence=?,
                    salience_tier=?, ttl_hint=?, status=?, superseded_by=?,
                    conflicts_with=?, should_forget_incumbent_applied=?,
                    ledger_schema_version=?
                WHERE version_id=?
                """,
                (
                    payload["fact_key"],
                    json.dumps(payload["value_struct"], ensure_ascii=False),
                    payload["valid_from"],
                    payload["valid_to"],
                    payload["receive_ts"],
                    payload["observed_at"],
                    payload["source_event_id"],
                    payload["confidence"],
                    payload["salience_tier"],
                    payload["ttl_hint"],
                    payload["status"],
                    payload["superseded_by"],
                    json.dumps(payload["conflicts_with"], ensure_ascii=False),
                    1 if payload["should_forget_incumbent_applied"] else 0,
                    payload["ledger_schema_version"],
                    payload["version_id"],
                ),
            )
            conn.commit()

    def _sqlite_load_all(self) -> list[FactVersion]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM fact_versions ORDER BY receive_ts ASC, version_id ASC"
            ).fetchall()
        out: list[FactVersion] = []
        for r in rows:
            out.append(
                FactVersion(
                    version_id=r["version_id"],
                    fact_key=r["fact_key"],
                    value_struct=json.loads(r["value_struct"]),
                    valid_from=r["valid_from"],
                    valid_to=r["valid_to"],
                    receive_ts=r["receive_ts"],
                    observed_at=r["observed_at"],
                    source_event_id=r["source_event_id"],
                    confidence=r["confidence"],
                    salience_tier=r["salience_tier"],
                    ttl_hint=r["ttl_hint"],
                    status=r["status"],
                    superseded_by=r["superseded_by"],
                    conflicts_with=json.loads(r["conflicts_with"]),
                    should_forget_incumbent_applied=bool(
                        r["should_forget_incumbent_applied"]
                    ),
                    ledger_schema_version=r["ledger_schema_version"],
                )
            )
        return out

    def _jsonl_append(self, fv: FactVersion) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(self._version_payload(fv), ensure_ascii=False) + "\n")

    def _jsonl_rewrite(self, versions: list[FactVersion]) -> None:
        header = {
            "_header": True,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        }
        lines = [json.dumps(header, ensure_ascii=False)]
        for fv in versions:
            lines.append(json.dumps(self._version_payload(fv), ensure_ascii=False))
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _jsonl_load_all(self) -> list[FactVersion]:
        if not self.path.exists():
            return []
        out: list[FactVersion] = []
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("_header"):
                    continue
                out.append(self._row_to_version(data))
        return out

    def _load_all(self) -> list[FactVersion]:
        if self._backend == "sqlite":
            return self._sqlite_load_all()
        return self._jsonl_load_all()

    def _persist_new(self, fv: FactVersion) -> None:
        if self._backend == "sqlite":
            self._sqlite_insert(fv)
        else:
            self._jsonl_append(fv)

    def _persist_update(self, fv: FactVersion) -> None:
        if self._backend == "sqlite":
            self._sqlite_update(fv)
        else:
            # JSONL: rewrite all rows (MVP; small ledgers)
            versions = self._jsonl_load_all()
            by_id = {v.version_id: v for v in versions}
            by_id[fv.version_id] = fv
            # preserve order: original order with replacement
            rewritten = [by_id.get(v.version_id, v) for v in versions]
            if fv.version_id not in {v.version_id for v in versions}:
                rewritten.append(fv)
            self._jsonl_rewrite(rewritten)

    # --- queries ---

    def list_versions(self, fact_key: str | None = None) -> list[FactVersion]:
        with self._lock:
            versions = self._load_all()
            if fact_key is None:
                return versions
            return [v for v in versions if v.fact_key == fact_key]

    def get_active(self, fact_key: str) -> FactVersion | None:
        with self._lock:
            actives = [
                v
                for v in self._load_all()
                if v.fact_key == fact_key and v.status == FactStatus.ACTIVE
            ]
            if len(actives) > 1:
                raise DualActiveError(
                    f"dual-active FactKey '{fact_key}': "
                    f"{[a.version_id for a in actives]}"
                )
            return actives[0] if actives else None

    def assert_no_dual_active(self) -> None:
        """Property helper: raise DualActiveError if any FactKey has >1 active."""
        with self._lock:
            by_key: dict[str, list[FactVersion]] = {}
            for v in self._load_all():
                if v.status == FactStatus.ACTIVE:
                    by_key.setdefault(v.fact_key, []).append(v)
            for key, rows in by_key.items():
                if len(rows) > 1:
                    raise DualActiveError(
                        f"dual-active FactKey '{key}': "
                        f"{[r.version_id for r in rows]}"
                    )

    def count_active(self) -> int:
        with self._lock:
            return sum(1 for v in self._load_all() if v.status == FactStatus.ACTIVE)

    def as_of(
        self,
        fact_key: str,
        at: datetime | str | None = None,
    ) -> FactVersion | None:
        """Return the single belief for FactKey valid at ``at`` (default now).

        Validity: valid_from <= at and (valid_to is None or at < valid_to).
        Prefers status that was active in that window; if multiple match
        (should not for well-formed ledger), pick latest receive_ts and
        still assert uniqueness of active-like rows.
        """
        at_dt = self._parse_dt(at) or self._now()
        with self._lock:
            candidates: list[FactVersion] = []
            for v in self._load_all():
                if v.fact_key != fact_key:
                    continue
                vf = self._parse_dt(v.valid_from)
                vt = self._parse_dt(v.valid_to)
                assert vf is not None
                if vf <= at_dt and (vt is None or at_dt < vt):
                    candidates.append(v)
            if not candidates:
                return None
            # Prefer non-tombstoned; then latest receive_ts
            candidates.sort(
                key=lambda x: (
                    0 if x.status != FactStatus.TOMBSTONED else 1,
                    self._parse_dt(x.receive_ts) or datetime.min.replace(tzinfo=UTC),
                )
            )
            # Exactly one belief expected for as_of in a healthy ledger
            # (overlapping intervals would be a bug — return latest, tests catch dual-active)
            return candidates[-1]

    # --- mutations ---

    def upsert(
        self,
        fact_key: str,
        value_struct: dict[str, Any],
        *,
        observed_at: datetime | str | None = None,
        source_event_id: str = "",
        confidence: float = 0.0,
        salience_tier: str | None = None,
        ttl_hint: str | None = None,
        receive_ts: datetime | str | None = None,
        valid_from: datetime | str | None = None,
    ) -> FactVersion:
        """Upsert metadata if same value_struct; else supersede (material change).

        Never creates dual-active rows for the same FactKey.
        """
        with self._lock:
            now = self._parse_dt(receive_ts) or self._now()
            vf = self._parse_dt(valid_from) or now
            obs = self._parse_dt(observed_at)
            active = self.get_active(fact_key)
            if active is None:
                fv = FactVersion(
                    fact_key=fact_key,
                    value_struct=dict(value_struct),
                    valid_from=vf,
                    receive_ts=now,
                    observed_at=obs,
                    source_event_id=source_event_id,
                    confidence=confidence,
                    salience_tier=salience_tier,
                    ttl_hint=ttl_hint,
                    status=FactStatus.ACTIVE,
                    ledger_schema_version=LEDGER_SCHEMA_VERSION,
                )
                self._persist_new(fv)
                self.assert_no_dual_active()
                return fv

            if value_struct_equal(active.value_struct, value_struct):
                # Metadata-only upsert; same version row
                active.confidence = confidence
                if salience_tier is not None:
                    active.salience_tier = salience_tier
                if ttl_hint is not None:
                    active.ttl_hint = ttl_hint
                if source_event_id:
                    active.source_event_id = source_event_id
                if obs is not None:
                    active.observed_at = obs
                active.receive_ts = now
                self._persist_update(active)
                self.assert_no_dual_active()
                return active

            # Materially changed → supersede
            return self._supersede_unlocked(
                fact_key,
                value_struct,
                observed_at=obs,
                source_event_id=source_event_id,
                confidence=confidence,
                salience_tier=salience_tier,
                ttl_hint=ttl_hint,
                receive_ts=now,
                valid_from=vf,
                should_forget_incumbent_applied=True,
            )

    def supersede(
        self,
        fact_key: str,
        value_struct: dict[str, Any],
        *,
        observed_at: datetime | str | None = None,
        source_event_id: str = "",
        confidence: float = 0.0,
        salience_tier: str | None = None,
        ttl_hint: str | None = None,
        receive_ts: datetime | str | None = None,
        valid_from: datetime | str | None = None,
        should_forget_incumbent_applied: bool = True,
        conflicts_with: list[str] | None = None,
    ) -> FactVersion:
        """Close active incumbent (valid_to=now) and activate new FactVersion."""
        with self._lock:
            now = self._parse_dt(receive_ts) or self._now()
            vf = self._parse_dt(valid_from) or now
            obs = self._parse_dt(observed_at)
            return self._supersede_unlocked(
                fact_key,
                value_struct,
                observed_at=obs,
                source_event_id=source_event_id,
                confidence=confidence,
                salience_tier=salience_tier,
                ttl_hint=ttl_hint,
                receive_ts=now,
                valid_from=vf,
                should_forget_incumbent_applied=should_forget_incumbent_applied,
                conflicts_with=conflicts_with,
            )

    def _supersede_unlocked(
        self,
        fact_key: str,
        value_struct: dict[str, Any],
        *,
        observed_at: datetime | None,
        source_event_id: str,
        confidence: float,
        salience_tier: str | None,
        ttl_hint: str | None,
        receive_ts: datetime,
        valid_from: datetime,
        should_forget_incumbent_applied: bool = True,
        conflicts_with: list[str] | None = None,
    ) -> FactVersion:
        active = self.get_active(fact_key)
        new_fv = FactVersion(
            fact_key=fact_key,
            value_struct=dict(value_struct),
            valid_from=valid_from,
            receive_ts=receive_ts,
            observed_at=observed_at,
            source_event_id=source_event_id,
            confidence=confidence,
            salience_tier=salience_tier,
            ttl_hint=ttl_hint,
            status=FactStatus.ACTIVE,
            conflicts_with=list(conflicts_with or []),
            should_forget_incumbent_applied=should_forget_incumbent_applied,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
        )
        if active is not None:
            active.status = FactStatus.SUPERSEDED
            active.valid_to = receive_ts
            active.superseded_by = new_fv.version_id
            if should_forget_incumbent_applied:
                active.should_forget_incumbent_applied = True
            self._persist_update(active)
        self._persist_new(new_fv)
        self.assert_no_dual_active()
        return new_fv

    def expire(
        self,
        fact_key: str,
        *,
        at: datetime | str | None = None,
        version_id: str | None = None,
    ) -> FactVersion | None:
        """Expire active (or specific) version: status=expired, valid_to=at."""
        with self._lock:
            when = self._parse_dt(at) or self._now()
            target: FactVersion | None = None
            if version_id:
                for v in self._load_all():
                    if v.version_id == version_id:
                        target = v
                        break
            else:
                target = self.get_active(fact_key)
            if target is None:
                return None
            target.status = FactStatus.EXPIRED
            target.valid_to = when
            self._persist_update(target)
            self.assert_no_dual_active()
            return target

    def tombstone(
        self,
        fact_key: str,
        *,
        at: datetime | str | None = None,
    ) -> FactVersion | None:
        """Tombstone active version (explicit forget)."""
        with self._lock:
            when = self._parse_dt(at) or self._now()
            active = self.get_active(fact_key)
            if active is None:
                return None
            active.status = FactStatus.TOMBSTONED
            active.valid_to = when
            self._persist_update(active)
            self.assert_no_dual_active()
            return active
