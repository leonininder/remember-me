"""remember-me — agents forget; this decides what to hydrate.

Local candidates first. Jev never ranks. Jev only admits.
"""

from remember_me.audit import GateAuditRecord, GateAuditStore
from remember_me.fanout import FANOUT_DEFAULTS, FanOutDefaults
from remember_me.gates import (
    EmitEgressGate,
    EmitGate,
    MemoryGate,
    RetainAdmitGate,
    WritebackGate,
)
from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev, HttpJev
from remember_me.pipeline import DualGatePipeline, MemoryPipeline
from remember_me.policy import (
    T_ACCEPT,
    T_ESCALATE,
    assert_no_rerank,
    escalate_human,
    map_emit_action,
    map_hydrate_action,
    map_writeback_action,
)
from remember_me.redact import redact_state
from remember_me.retrieve import LocalCandidateRetriever
from remember_me.types import (
    JEV_MODEL_PIN,
    AdmitDecision,
    Candidate,
    DualGateResult,
    EmitAction,
    EmitDecision,
    EscalationRecord,
    GateDecision,
    Horizon,
    HydrateAction,
    Marker,
    NodeKind,
    PipelineResult,
    WritebackAction,
    WritebackDecision,
)

__version__ = "0.1.0"

__all__ = [
    "GateAuditRecord",
    "GateAuditStore",
    "AdmitDecision",
    "Candidate",
    "DualGatePipeline",
    "DualGateResult",
    "EmitAction",
    "EmitDecision",
    "EmitEgressGate",
    "EmitGate",
    "EscalationRecord",
    "FANOUT_DEFAULTS",
    "FakeJev",
    "FanOutDefaults",
    "GateDecision",
    "Horizon",
    "HttpJev",
    "HydrateAction",
    "JEV_MODEL_PIN",
    "LocalCandidateRetriever",
    "Marker",
    "MemoryGate",
    "MemoryPipeline",
    "NodeKind",
    "PipelineResult",
    "RetainAdmitGate",
    "T_ACCEPT",
    "T_ESCALATE",
    "TopologyGraph",
    "WritebackAction",
    "WritebackDecision",
    "WritebackGate",
    "assert_no_rerank",
    "escalate_human",
    "map_emit_action",
    "map_hydrate_action",
    "map_writeback_action",
    "redact_state",
    "__version__",
]
