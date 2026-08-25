"""End-to-end graph checks with a deterministic LLM test double.

The production nodes always use a configured provider. This double only makes graph topology,
retry bounds, and HITL behavior testable in CI where API credentials are deliberately absent.
"""

from __future__ import annotations

from langgraph_agent_lab import nodes
from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.scenarios import load_scenarios
from langgraph_agent_lab.state import initial_state


class OfflineLLM:
    """Small structured-output-compatible test double."""

    schema: type | None = None

    def with_structured_output(self, schema: type) -> OfflineLLM:
        self.schema = schema
        return self

    def invoke(self, prompt: str):
        if self.schema is not None:
            ticket = prompt.rsplit("Ticket: ", maxsplit=1)[-1].lower()
            route = (
                "risky"
                if any(word in ticket for word in ("refund", "delete", "send confirmation"))
                else "tool"
                if any(word in ticket for word in ("lookup", "order status"))
                else "missing_info"
                if ticket == "can you fix it?"
                else "error"
                if any(word in ticket for word in ("timeout", "system failure"))
                else "simple"
            )
            return self.schema(route=route, rationale="offline topology test")
        return type("Response", (), {"content": "Grounded response from test double."})()


def test_all_sample_routes_terminate_without_provider(monkeypatch) -> None:
    """All sample paths compile, terminate, and preserve their classified route."""
    monkeypatch.setattr(nodes, "get_llm", lambda: OfflineLLM())
    graph = build_graph(checkpointer=build_checkpointer("memory"))

    for scenario in load_scenarios("data/sample/scenarios.jsonl"):
        state = initial_state(scenario)
        config = {"configurable": {"thread_id": state["thread_id"]}}
        result = graph.invoke(state, config=config)

        assert result["route"] == scenario.expected_route.value
        assert result.get("final_answer") or result.get("pending_question")
        assert any(event["node"] == "finalize" for event in result["events"])
        if scenario.requires_approval:
            assert result["approval"]["approved"] is True


def test_dead_letter_stops_at_configured_retry_limit(monkeypatch) -> None:
    """A nonrecoverable error reaches dead letter instead of looping indefinitely."""
    monkeypatch.setattr(nodes, "get_llm", lambda: OfflineLLM())
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    scenario = next(
        item for item in load_scenarios("data/sample/scenarios.jsonl") if item.id == "S07_dead_letter"
    )
    state = initial_state(scenario)
    result = graph.invoke(state, config={"configurable": {"thread_id": state["thread_id"]}})

    assert result["attempt"] == scenario.max_attempts
    assert any(event["node"] == "dead_letter" for event in result["events"])
