"""In-memory (and optional SQLite) topology graph store with horizons and TTL."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from remember_me.types import Edge, Horizon, Marker, NodeKind

DEFAULT_TTL: dict[Horizon, timedelta] = {
    Horizon.WORKING: timedelta(minutes=60),
    Horizon.SESSION: timedelta(days=2),
    Horizon.DURABLE: timedelta(days=365 * 10),
}


class TopologyGraph:
    """Topology graph of memory markers. Bodies stay at content_ref / content."""

    def __init__(self) -> None:
        self._nodes: dict[str, Marker] = {}
        self._edges: list[Edge] = []

    def __len__(self) -> int:
        return len(self._nodes)

    def upsert(self, marker: Marker, *, apply_default_ttl: bool = True) -> Marker:
        """Insert or replace a marker; optionally stamp default TTL by horizon."""
        if apply_default_ttl and marker.ttl_expires_at is None:
            ttl = DEFAULT_TTL.get(marker.horizon, timedelta(hours=1))
            marker = marker.model_copy(update={"ttl_expires_at": datetime.now(UTC) + ttl})
        self._nodes[marker.node_id] = marker
        self._recompute_degrees()
        return self._nodes[marker.node_id]

    def get(self, node_id: str) -> Marker | None:
        return self._nodes.get(node_id)

    def delete(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._edges = [e for e in self._edges if e.source_id != node_id and e.target_id != node_id]
        self._recompute_degrees()
        return True

    def add_edge(self, edge: Edge) -> None:
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise KeyError("both endpoints must exist before adding an edge")
        self._edges.append(edge)
        self._recompute_degrees()

    def edges(self) -> list[Edge]:
        return list(self._edges)

    def all_markers(self, *, include_expired: bool = False) -> list[Marker]:
        now = datetime.now(UTC)
        out: list[Marker] = []
        for m in self._nodes.values():
            if not include_expired and m.ttl_expires_at and m.ttl_expires_at < now:
                continue
            if m.invalid_at and m.invalid_at < now:
                continue
            out.append(m)
        return out

    def by_horizon(self, horizon: Horizon) -> list[Marker]:
        return [m for m in self.all_markers() if m.horizon == horizon]

    def by_kind(self, kind: NodeKind) -> list[Marker]:
        return [m for m in self.all_markers() if m.kind == kind]

    def by_tag(self, tag: str) -> list[Marker]:
        return [m for m in self.all_markers() if tag in m.tags]

    def touch(self, node_id: str) -> Marker | None:
        m = self._nodes.get(node_id)
        if m is None:
            return None
        updated = m.model_copy(update={"last_touch": datetime.now(UTC)})
        self._nodes[node_id] = updated
        return updated

    def purge_expired(self) -> int:
        """Remove TTL-expired working/session nodes. Durable markers are invalidated, not erased."""
        now = datetime.now(UTC)
        remove: list[str] = []
        for nid, m in self._nodes.items():
            if m.ttl_expires_at and m.ttl_expires_at < now:
                if m.horizon == Horizon.DURABLE:
                    self._nodes[nid] = m.model_copy(update={"invalid_at": now})
                else:
                    remove.append(nid)
        for nid in remove:
            self.delete(nid)
        return len(remove)

    def promote(self, node_id: str, horizon: Horizon = Horizon.DURABLE) -> Marker | None:
        m = self._nodes.get(node_id)
        if m is None:
            return None
        ttl = DEFAULT_TTL.get(horizon)
        updates: dict = {"horizon": horizon, "last_touch": datetime.now(UTC)}
        if ttl is not None:
            updates["ttl_expires_at"] = datetime.now(UTC) + ttl
        updated = m.model_copy(update=updates)
        self._nodes[node_id] = updated
        return updated

    def observe(
        self,
        *,
        node_id: str,
        content: str,
        content_ref: str | None = None,
        kind: NodeKind = NodeKind.FACT,
        horizon: Horizon = Horizon.WORKING,
        tags: Iterable[str] | None = None,
        salience: float = 0.5,
        provenance: str = "observe",
    ) -> Marker:
        """Write a marker from an observation (body off-context via content_ref)."""
        marker = Marker(
            node_id=node_id,
            kind=kind,
            horizon=horizon,
            content_ref=content_ref or f"local://{node_id}",
            content=content,
            tags=list(tags or []),
            salience=salience,
            provenance=provenance,
        )
        return self.upsert(marker)

    def _recompute_degrees(self) -> None:
        counts: dict[str, int] = {nid: 0 for nid in self._nodes}
        for e in self._edges:
            if e.source_id in counts:
                counts[e.source_id] += 1
            if e.target_id in counts:
                counts[e.target_id] += 1
        for nid, deg in counts.items():
            m = self._nodes[nid]
            if m.degree != deg:
                self._nodes[nid] = m.model_copy(update={"degree": deg})

    # --- optional SQLite persistence ---

    def save_sqlite(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS markers (
                    node_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute("DELETE FROM markers")
            conn.execute("DELETE FROM edges")
            for m in self._nodes.values():
                conn.execute(
                    "INSERT INTO markers(node_id, payload) VALUES (?, ?)",
                    (m.node_id, m.model_dump_json()),
                )
            for e in self._edges:
                conn.execute("INSERT INTO edges(payload) VALUES (?)", (e.model_dump_json(),))
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def load_sqlite(cls, path: str | Path) -> TopologyGraph:
        g = cls()
        conn = sqlite3.connect(path)
        try:
            rows = conn.execute("SELECT payload FROM markers").fetchall()
            for (payload,) in rows:
                g._nodes[json.loads(payload)["node_id"]] = Marker.model_validate_json(payload)
            erows = conn.execute("SELECT payload FROM edges").fetchall()
            for (payload,) in erows:
                g._edges.append(Edge.model_validate_json(payload))
            g._recompute_degrees()
        finally:
            conn.close()
        return g
