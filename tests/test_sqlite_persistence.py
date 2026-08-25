"""Durable-checkpoint evidence for the SQLite bonus extension."""

from __future__ import annotations

from langgraph_agent_lab import nodes
from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


class OfflineLLM:
    """Minimal LLM double used only to exercise persistence without network access."""

    def with_structured_output(self, schema: type) -> OfflineLLM:
        self.schema = schema
        return self

    def invoke(self, _prompt: str):
        if hasattr(self, "schema"):
            return self.schema(route="simple", rationale="persistence test")
        return type("Response", (), {"content": "Persisted grounded response."})()


def test_sqlite_checkpoint_survives_new_checkpointer(tmp_path, monkeypatch) -> None:
    """A new graph instance reads the completed state written by its predecessor."""
    monkeypatch.setattr(nodes, "get_llm", lambda: OfflineLLM())
    database_path = tmp_path / "checkpoints.sqlite"
    scenario = Scenario(id="sqlite-recovery", query="How do I reset my password?", expected_route=Route.SIMPLE)
    state = initial_state(scenario)
    config = {"configurable": {"thread_id": state["thread_id"]}}

    first_checkpointer = build_checkpointer("sqlite", str(database_path))
    build_graph(first_checkpointer).invoke(state, config=config)

    recovered_graph = build_graph(build_checkpointer("sqlite", str(database_path)))
    recovered_state = recovered_graph.get_state(config)

    assert recovered_state.values["final_answer"]
    assert recovered_state.values["route"] == Route.SIMPLE.value
    assert any(snapshot.values for snapshot in recovered_graph.get_state_history(config))
