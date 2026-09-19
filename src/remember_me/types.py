"""Core types for topology graph memory markers and Jev decision payloads.

Jev is a calibrated decision gate — not a store and not a similarity ranker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Horizon(StrEnum):
    """Three-horizon memory design (working / session / durable)."""

    WORKING = "working"
    SESSION = "session"
    DURABLE = "durable"


class NodeKind(StrEnum):
    """Closed taxonomy for memory node kinds."""

    FACT = "fact"
    EPISODE = "episode"
    PROCEDURE = "procedure"
    ARTIFACT = "artifact"
    EDGE = "edge"


class HydrateAction(StrEnum):
    """Closed Choice taxonomy for post-recall hydrate decisions."""

    HYDRATE_FULL = "hydrate_full"
    STUB_ONLY = "stub_only"
    SKIP = "skip"
    PROMOTE_DURABLE = "promote_durable"
    OTHER = "other"


class NetworkRoute(StrEnum):
    """Optional memory-network routing Choice."""

    WORLD = "world"
    EXPERIENCE = "experience"
    OBSERVATION = "observation"
    OPINION = "opinion"
    SKIP = "skip"


class AdmitDecision(StrEnum):
    """Retain/admit Choice for new markers."""

    ADMIT = "admit"
    REJECT = "reject"
    DEFER = "defer"


class Marker(BaseModel):
    """Topology node marker. Body lives at content_ref; never sent to Jev."""

    node_id: str
    horizon: Horizon = Horizon.WORKING
    kind: NodeKind = NodeKind.FACT
    content_ref: str
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    ttl_expires_at: datetime | None = None
    provenance: str = "local"
    tags: list[str] = Field(default_factory=list)
    valid_at: datetime | None = None
    invalid_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_touch: datetime = Field(default_factory=lambda: datetime.now(UTC))
    degree: int = Field(default=0, ge=0)
    # Local body for fixture / demo only; never included in redacted outbound state.
    content: str | None = None
    # Optional secret field used only in tests to prove redaction.
    secret: str | None = None

    @field_validator("node_id")
    @classmethod
    def _nonempty_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("node_id must be non-empty")
        return v.strip()


class Edge(BaseModel):
    """Directed edge between markers."""

    source_id: str
    target_id: str
    relation: str = "related"
    weight: float = Field(default=1.0, ge=0.0)


class Candidate(BaseModel):
    """Local retrieval hit before Jev gating."""

    node_id: str
    kind: NodeKind
    tags: list[str] = Field(default_factory=list)
    degree: int = 0
    last_touch: datetime
    local_score: float = Field(ge=0.0)
    tokens_est: int = Field(default=32, ge=0)
    horizon: Horizon = Horizon.WORKING
    content_ref: str = ""
    # Present only in local pipeline; stripped by redact_state.
    content: str | None = None


class RedactedCandidate(BaseModel):
    """Outbound-safe candidate fields for Jev. No content, secrets, or PII."""

    node_id: str
    kind: NodeKind
    tags: list[str]
    degree: int
    last_touch: datetime
    local_score: float
    tokens_est: int


class JevQuestionResult(BaseModel):
    """Single calibrated answer from a Jev batch request."""

    question_id: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    raw: dict[str, Any] = Field(default_factory=dict)


class JevBatchResponse(BaseModel):
    """Batch multi-question Jev response for one candidate (or set)."""

    node_id: str
    results: dict[str, JevQuestionResult] = Field(default_factory=dict)
    error: str | None = None
    denied: bool = False
    malformed: bool = False
    timed_out: bool = False

    @property
    def failed(self) -> bool:
        return bool(self.error or self.denied or self.malformed or self.timed_out)


class GateDecision(BaseModel):
    """Policy outcome for one candidate after Jev + thresholds."""

    node_id: str
    action: HydrateAction
    confidence: float
    need_score: float | None = None
    still_matters: bool | None = None
    network_route: NetworkRoute | None = None
    trigger_reflect: bool | None = None
    fail_closed: bool = False
    reason: str = ""
    local_score: float = 0.0


class HydratedNode(BaseModel):
    """Node allowed into LLM context after gate + policy."""

    node_id: str
    kind: NodeKind
    content: str
    content_ref: str
    action: HydrateAction
    confidence: float
    stub: bool = False


class PipelineResult(BaseModel):
    """End-to-end observe→retrieve→redact→jev→hydrate outcome."""

    query: str
    candidates: list[Candidate]
    redacted: list[RedactedCandidate]
    decisions: list[GateDecision]
    hydrated: list[HydratedNode]
    jev_called: bool = False
    fail_closed_count: int = 0


class AdmitResult(BaseModel):
    """Retain/admit gate outcome for a proposed marker."""

    node_id: str
    decision: AdmitDecision
    kind: NodeKind
    confidence: float
    fail_closed: bool = False
    reason: str = ""


# Question ID registry (pin with FakeJev / HttpJev)
Q_HYDRATE_ACTION = "hydrate_action"
Q_NEED_FOR_NEXT_TURN = "need_for_next_turn"
Q_STILL_MATTERS = "still_matters_for_latest_ask"
Q_NETWORK_ROUTE = "memory_network"
Q_TRIGGER_REFLECT = "trigger_reflect"
Q_ADMIT = "admit"
Q_NODE_KIND = "node_kind"

JEV_MODEL_PIN = "jev-1.13.0"

SECRET_FIELD_NAMES = frozenset(
    {
        "secret",
        "content",
        "body",
        "password",
        "api_key",
        "token",
        "ssn",
        "email",
        "phone",
    }
)
