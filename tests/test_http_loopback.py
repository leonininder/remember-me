"""Real loopback HTTP tests for wire types, IDs, and fail-closed pipeline behavior."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from remember_me import HttpJev, MemoryPipeline, TopologyGraph


@pytest.fixture
def wire_server():
    state = {"mutate": lambda answers: None, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(payload)
            answers = {}
            for key, question in payload["questions"].items():
                kind = question["type"]
                answer = {"type": kind, "confidence": 0.99}
                answer.update({"choice": "hydrate_full"} if kind == "choice" else
                              {"score": 4} if kind == "score" else {"noul": 0.99})
                answers[key] = answer
            state["mutate"](answers)
            encoded = json.dumps({"answers": answers}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{server.server_port}/v1/systemone"
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def run_pipeline(server, *, batch=True):
    graph = TopologyGraph()
    for node_id in ("team", "team__build"):
        graph.observe(node_id=node_id, content="private body build", tags=["build"])
    client = HttpJev(api_key="local-test-only", base_url=server["url"], batch_candidates=batch)
    return MemoryPipeline(graph, client).run("build raw-query-must-stay-local")


@pytest.mark.parametrize("batch", [True, False])
def test_real_http_roundtrip_and_request_boundary(wire_server, batch):
    result = run_pipeline(wire_server, batch=batch)
    assert {node.node_id for node in result.hydrated} == {"team", "team__build"}
    payloads = json.dumps(wire_server["requests"])
    assert "private body" not in payloads
    assert "raw-query-must-stay-local" not in payloads


@pytest.mark.parametrize("field,value", [
    ("score", "not-a-number"), ("score", True), ("score", []),
    ("score", float("nan")), ("score", float("inf")), ("score", 10 ** 400),
    ("noul", "false"), ("noul", True), ("noul", []), ("noul", float("nan")),
    ("noul", float("inf")), ("noul", -0.001), ("noul", 1.001),
    ("confidence", "0.99"), ("confidence", True), ("confidence", float("nan")),
    ("confidence", 1.001), ("confidence", 10 ** 400),
])
def test_real_http_invalid_values_fail_closed(wire_server, field, value):
    def mutate(answers):
        for answer in answers.values():
            if field in answer:
                answer[field] = value
    wire_server["mutate"] = mutate
    result = run_pipeline(wire_server)
    assert not result.hydrated
    assert result.fail_closed_count == 2


@pytest.mark.parametrize("batch", [True, False])
def test_real_http_wrong_question_type_fail_closed(wire_server, batch):
    def mutate(answers):
        for key in answers:
            if key.endswith("still_matters_for_latest_ask"):
                answers[key] = {"type": "choice", "choice": "false", "confidence": 0.99}
    wire_server["mutate"] = mutate
    result = run_pipeline(wire_server, batch=batch)
    assert not result.hydrated
    assert result.fail_closed_count == 2


def test_real_http_missing_required_answer_fail_closed(wire_server):
    def mutate(answers):
        for key in list(answers):
            if key.endswith("still_matters_for_latest_ask"):
                del answers[key]
    wire_server["mutate"] = mutate
    result = run_pipeline(wire_server)
    assert not result.hydrated
    assert result.fail_closed_count == 2
