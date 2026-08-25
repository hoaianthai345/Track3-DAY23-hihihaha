"""Demo đơn giản: chạy một case thật (mặc định S07_dead_letter) qua graph đã build,
in ra route đi qua từng node và audit trail — dùng để trình bày / nghiệm thu trực tiếp.

Usage:
    python demo_case.py                # mặc định S07_dead_letter
    python demo_case.py S05_error       # chọn scenario khác theo id
"""

from __future__ import annotations

import sys

from src.langgraph_agent_lab.graph import build_graph
from src.langgraph_agent_lab.scenarios import load_scenarios
from src.langgraph_agent_lab.state import initial_state

SCENARIO_ID = sys.argv[1] if len(sys.argv) > 1 else "S07_dead_letter"


def main() -> None:
    scenarios = {s.id: s for s in load_scenarios("data/sample/scenarios.jsonl")}
    if SCENARIO_ID not in scenarios:
        print(f"Không tìm thấy scenario '{SCENARIO_ID}'. Có: {list(scenarios)}")
        return
    scenario = scenarios[SCENARIO_ID]

    print(f"=== Case: {scenario.id} ===")
    print(f"Query: {scenario.query!r}")
    print(f"Expected route: {scenario.expected_route.value}  |  max_attempts: {scenario.max_attempts}\n")

    graph = build_graph(checkpointer=None)
    state = initial_state(scenario)
    run_config = {"configurable": {"thread_id": state["thread_id"]}}
    final_state = graph.invoke(state, config=run_config)

    print("--- Node path (audit events) ---")
    for i, ev in enumerate(final_state.get("events", []), start=1):
        meta = {k: v for k, v in ev.get("metadata", {}).items() if k != "rationale"}
        meta_str = f"  {meta}" if meta else ""
        print(f"{i:2d}. [{ev['node']:<14}] {ev['event_type']:<16} {ev['message']}{meta_str}")

    print("\n--- Kết quả ---")
    print(f"actual_route : {final_state.get('route')}")
    print(f"attempt      : {final_state.get('attempt')}")
    print(f"tool_results : {final_state.get('tool_results')}")
    print(f"errors       : {final_state.get('errors')}")
    print(f"final_answer : {final_state.get('final_answer')}")

    match = "✅ ĐÚNG" if final_state.get("route") == scenario.expected_route.value else "❌ SAI"
    print(f"\nSo với expected_route: {match}")


if __name__ == "__main__":
    main()
