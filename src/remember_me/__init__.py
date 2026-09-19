"""remember-me — agents forget; this decides what to hydrate.

Local recall finds candidates; TypeSafe Jev gates include / stub / skip /
promote AFTER retrieval on a redacted set. Jev is NOT the store and NOT
the similarity ranker. Import as ``remember_me``; CLI is ``remember-me``.
"""

from remember_me.gates import MemoryGate, RetainAdmitGate
from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev, HttpJev
from remember_me.pipeline import MemoryPipeline
from remember_me.policy import T_ACCEPT, T_ESCALATE
from remember_me.redact import redact_state
from remember_me.retrieve import LocalCandidateRetriever
from remember_me.types import (
    JEV_MODEL_PIN,
    AdmitDecision,
    Candidate,
    GateDecision,
    Horizon,
    HydrateAction,
    Marker,
    NodeKind,
    PipelineResult,
)

__version__ = "0.1.0"

__all__ = [
    "AdmitDecision",
    "Candidate",
    "FakeJev",
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
    "redact_state",
    "__version__",
]
