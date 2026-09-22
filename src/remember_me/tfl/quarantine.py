"""QuarantineQueue — spill-to-disk, no drop, no md-append (PLAN §4.8)."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from remember_me.tfl.types import QuarantineItem

DEFAULT_BOUND_N = 256


class QuarantineBlockedError(RuntimeError):
    """Spill exhausted / disk failure — block new auto-admits + escalate."""


class QuarantineQueue:
    """In-memory bound N with overflow spill-to-disk only.

    David R2 #4: **forbid drop**. Never discard CandidateFacts.
    Explicit ban: no fallback writing prose into MEMORY.md / AGENTS.md.
    """

    def __init__(
        self,
        *,
        bound_n: int = DEFAULT_BOUND_N,
        spill_dir: str | Path | None = None,
        max_spill_items: int | None = 100_000,
    ) -> None:
        if bound_n < 1:
            raise ValueError("bound_n must be >= 1")
        self.bound_n = bound_n
        self.spill_dir = Path(spill_dir) if spill_dir else None
        self.max_spill_items = max_spill_items
        self._lock = threading.Lock()
        self._mem: list[QuarantineItem] = []
        self._spill_count = 0
        self._blocked = False
        self._block_reason = ""
        if self.spill_dir is not None:
            self.spill_dir.mkdir(parents=True, exist_ok=True)
            self._spill_count = self._count_spill_files()

    @property
    def blocked(self) -> bool:
        return self._blocked

    @property
    def block_reason(self) -> str:
        return self._block_reason

    def _spill_path(self, item: QuarantineItem) -> Path:
        assert self.spill_dir is not None
        return self.spill_dir / f"{item.id}.json"

    def _count_spill_files(self) -> int:
        if self.spill_dir is None or not self.spill_dir.exists():
            return 0
        return sum(1 for p in self.spill_dir.glob("*.json") if p.is_file())

    def enqueue(
        self,
        candidate: dict[str, Any] | QuarantineItem,
        *,
        reason: str = "",
        fact_key_hint: str | None = None,
        escalate_after: datetime | None = None,
    ) -> QuarantineItem:
        """Enqueue; spill to disk on overflow; never drop. Raises if blocked."""
        with self._lock:
            if self._blocked:
                raise QuarantineBlockedError(
                    self._block_reason or "quarantine blocked; escalate_human"
                )

            if isinstance(candidate, QuarantineItem):
                item = candidate
            else:
                item = QuarantineItem(
                    candidate=dict(candidate),
                    reason=reason,
                    fact_key_hint=fact_key_hint,
                    escalate_after=escalate_after,
                    enqueued_at=datetime.now(UTC),
                )

            if len(self._mem) < self.bound_n:
                self._mem.append(item)
                return item

            # Overflow → spill-to-disk only (forbid drop)
            if self.spill_dir is None:
                self._blocked = True
                self._block_reason = (
                    "in-memory quarantine full and no spill_dir; "
                    "block new auto-admits; escalate_human"
                )
                raise QuarantineBlockedError(self._block_reason)

            if (
                self.max_spill_items is not None
                and self._spill_count >= self.max_spill_items
            ):
                self._blocked = True
                self._block_reason = (
                    "quarantine spill exhausted; block new auto-admits; escalate_human"
                )
                raise QuarantineBlockedError(self._block_reason)

            try:
                path = self._spill_path(item)
                path.write_text(
                    json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
                    encoding="utf-8",
                )
                self._spill_count += 1
            except OSError as exc:
                self._blocked = True
                self._block_reason = (
                    f"quarantine spill failed ({exc}); "
                    "block new auto-admits; escalate_human"
                )
                raise QuarantineBlockedError(self._block_reason) from exc

            return item

    def peek_memory(self) -> list[QuarantineItem]:
        with self._lock:
            return list(self._mem)

    def spill_count(self) -> int:
        with self._lock:
            return self._spill_count

    def total_count(self) -> int:
        with self._lock:
            return len(self._mem) + self._spill_count

    def drain_memory(self, *, limit: int | None = None) -> list[QuarantineItem]:
        """Pop from memory head for human/Jev retry. Spill remains on disk."""
        with self._lock:
            if limit is None:
                out, self._mem = self._mem, []
                return out
            out = self._mem[:limit]
            self._mem = self._mem[limit:]
            return out

    def load_spill_item(self, item_id: str) -> QuarantineItem | None:
        if self.spill_dir is None:
            return None
        path = self.spill_dir / f"{item_id}.json"
        if not path.exists():
            return None
        return QuarantineItem.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def list_spill_ids(self) -> list[str]:
        if self.spill_dir is None or not self.spill_dir.exists():
            return []
        return sorted(p.stem for p in self.spill_dir.glob("*.json"))

    def acknowledge_spill(self, item_id: str) -> bool:
        """Remove one spilled item after human/Jev admit (not a silent drop of unknowns)."""
        if self.spill_dir is None:
            return False
        path = self.spill_dir / f"{item_id}.json"
        with self._lock:
            if not path.exists():
                return False
            path.unlink()
            self._spill_count = max(0, self._spill_count - 1)
            if (
                self._blocked
                and (self.max_spill_items is None or self._spill_count < self.max_spill_items)
                and "spill exhausted" in self._block_reason
            ):
                # Unblock when capacity frees; caller may re-try enqueue.
                self._blocked = False
                self._block_reason = ""
            return True
