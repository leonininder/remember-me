"""Controlled offline contract demo; forced decisions are not model-quality evidence."""

from remember_me import FakeJev, MemoryPipeline, TopologyGraph
from remember_me.types import HydrateAction


def main() -> None:
    graph = TopologyGraph()
    graph.observe(node_id="theme", content="Use dark theme", tags=["theme"])
    # Force a response to make the full-text branch reproducible without credentials.
    client = FakeJev(confidence_override=0.99, action_override=HydrateAction.HYDRATE_FULL)
    accepted = MemoryPipeline(graph, client).run("theme")
    assert [node.content for node in accepted.hydrated] == ["Use dark theme"]
    print("Forced offline acceptance:", accepted.hydrated[0].content)

    outage = MemoryPipeline(graph, FakeJev(force_timeout=True)).run("theme")
    assert not outage.hydrated
    assert outage.fail_closed_count == 1
    print("Simulated timeout: 0 memories loaded; 1 fail-closed decision")


if __name__ == "__main__":
    main()
