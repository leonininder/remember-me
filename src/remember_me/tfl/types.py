"""TFL v0 types: CandidateFact, FactVersion, QuarantineItem."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

LEDGER_SCHEMA_VERSION: Literal["tfl_ledger_v0"] = "tfl_ledger_v0"

ExtractMethod = Literal["deterministic", "llm_propose", "manual"]
SalienceHint = Literal["childhood_play", "adult_safety", "routine", "ephemeral"]

FORBIDDEN_SOLE_VALUE_KEYS = frozenset({"text", "body", "prose", "diary", "notes"})

VALUE_STRUCT_MAX_DEPTH = 3
VALUE_STRUCT_MAX_STRING = 128
VALUE_STRUCT_MAX_BYTES = 2048  # 2 KiB UTF-8 canonical


class FactStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    TOMBSTONED = "tombstoned"
    QUARANTINED = "quarantined"


class CandidateFact(BaseModel):
    """Closed CandidateFact (PLAN §4.2). Unknown properties rejected."""

    model_config = {"extra": "forbid"}

    entity: str
    attribute: str
    qualifier: str | None = None
    value_struct: dict[str, Any]
    observed_at: datetime
    source_event_id: str
    extract_method: ExtractMethod
    proposed_fact_key: str | None = None
    salience_hint: SalienceHint | None = None

    @field_validator("entity", "attribute")
    @classmethod
    def _nonempty_component(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("entity/attribute must be non-empty")
        return str(v).strip()

    @field_validator("source_event_id")
    @classmethod
    def _nonempty_source(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("source_event_id must be non-empty")
        return v.strip()

    @field_validator("value_struct")
    @classmethod
    def _value_is_object(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("value_struct must be an object")
        return v


class FactVersion(BaseModel):
    """One versioned belief row in the temporal ledger."""

    version_id: str = Field(default_factory=lambda: uuid4().hex)
    fact_key: str
    value_struct: dict[str, Any]
    valid_from: datetime
    valid_to: datetime | None = None
    receive_ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    observed_at: datetime | None = None
    source_event_id: str = ""
    confidence: float = 0.0
    salience_tier: str | None = None
    ttl_hint: str | None = None
    status: FactStatus = FactStatus.ACTIVE
    superseded_by: str | None = None
    conflicts_with: list[str] = Field(default_factory=list)
    should_forget_incumbent_applied: bool = False
    ledger_schema_version: str = LEDGER_SCHEMA_VERSION

    @field_validator("fact_key")
    @classmethod
    def _nonempty_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("fact_key must be non-empty")
        return v.strip()


class QuarantineItem(BaseModel):
    """Fail-closed holding for candidates that cannot auto-admit."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    candidate: dict[str, Any]
    reason: str
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attempts: int = 0
    escalate_after: datetime | None = None
    fact_key_hint: str | None = None


class ValidationResult(BaseModel):
    """Admit outcome: accept with minted key, or quarantine/reject."""

    ok: bool
    fact_key: str | None = None
    candidate: CandidateFact | None = None
    reason: str = ""
    quarantine: bool = False
