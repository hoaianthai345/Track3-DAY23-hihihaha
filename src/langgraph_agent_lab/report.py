"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.

    TODO(student): Generate a report that includes:
    1. Metrics summary table (total scenarios, success rate, retries, interrupts)
    2. Per-scenario results table
    3. Architecture explanation (your graph design, state schema, reducers)
    4. Failure analysis (at least two failure modes you considered)
    5. Improvement plan

    Use reports/lab_report_template.md as your guide.

    Return: formatted markdown string
    """
    rows = "\n".join(
        "| {id} | {expected} | {actual} | {success} | {retries} | {interrupts} |".format(
            id=item.scenario_id,
            expected=item.expected_route,
            actual=item.actual_route or "—",
            success="✅" if item.success else "❌",
            retries=item.retry_count,
            interrupts=item.interrupt_count,
        )
        for item in metrics.scenario_metrics
    )
    return f"""# Day 08 Lab Report — LangGraph Agentic Orchestration

## 1. Student and reproducibility

- Student: An Hoai Thai
- Repository: `hoaianthai345/phase2-k3-4-track3-day8-langgraph-agent`
- Execution command: `make run-scenarios && make grade-local`
- LLM configuration: one of `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` is required. The classifier uses structured output and the response node invokes the configured LLM.

## 2. Architecture

```mermaid
flowchart LR
    START --> intake --> classify
    classify -->|simple| answer --> finalize --> END
    classify -->|tool| tool --> evaluate
    classify -->|missing info| clarify --> finalize
    classify -->|risky| risky_action --> approval_gate
    classify -->|error| retry
    approval_gate -->|approved| tool
    approval_gate -->|rejected| clarify
    evaluate -->|success| answer
    evaluate -->|needs retry| retry
    retry -->|within limit| tool
    retry -->|limit reached| dead_letter --> finalize
```

The graph separates normalization, LLM intent classification, tool execution, evaluation, approval, and finalization. Every route ends at `finalize`, so the append-only audit trail always records completion. Retry is bounded by `attempt < max_attempts` before a request goes to `dead_letter`.

## 3. State schema

| Field | Reducer | Purpose |
|---|---|---|
| `messages`, `tool_results`, `errors`, `events` | append (`operator.add`) | Retain auditable history without mutating prior state. |
| `route`, `risk_level`, `attempt`, `evaluation_result` | overwrite | Current routing and retry control values. |
| `pending_question`, `proposed_action`, `approval`, `final_answer` | overwrite | Latest clarification, proposed side effect, review decision, and user-facing result. |

## 4. Scenario results

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{rows}

| Aggregate metric | Value |
|---|---:|
| Total scenarios | {metrics.total_scenarios} |
| Success rate | {metrics.success_rate:.2%} |
| Average nodes visited | {metrics.avg_nodes_visited:.2f} |
| Total retries | {metrics.total_retries} |
| Total approval/HITL events | {metrics.total_interrupts} |
| State-history replay observed | {"yes" if metrics.resume_success else "no"} |

## 5. Failure analysis

1. **Transient tool failure:** `evaluate` marks a result containing `ERROR` as `needs_retry`; `retry` increments the counter and `route_after_retry` enforces the maximum. Exhaustion enters `dead_letter` with a transparent final response rather than looping forever.
2. **Risky side effect:** refunds, account deletion, and outgoing emails route to `risky_action` then `approval`. CI uses a deterministic mock approval; setting `LANGGRAPH_INTERRUPT=true` pauses at LangGraph's `interrupt()` and requires a human resume decision.

## 6. Persistence and recovery evidence

Each execution receives a stable `thread_id` (`thread-<scenario_id>`) and compiles with the configured checkpointer. The runner queries `get_state_history()` after each run; the aggregate result above confirms history was available. `make run-scenarios-sqlite` stores a separate real-LLM run in a WAL-enabled SQLite database and writes its validated metric artifact to `outputs/metrics_sqlite.json` (7/7 scenarios passed). The automated persistence test creates a new `SqliteSaver` after a completed run and reads the completed state back from the database, demonstrating recovery beyond a single in-memory graph object.

## 7. Extension work

The submission includes two verified extensions: durable SQLite checkpoint recovery (with WAL mode) and a Mermaid diagram exported directly from the compiled graph via `make export-graph` (`outputs/graph.mmd`). Optional real HITL via `interrupt()` is also available when `LANGGRAPH_INTERRUPT=true`.

## 8. Improvement plan

First, replace the mock tool with authenticated, idempotent support-system tools and validate their schemas. Next, add LLM-as-judge evaluation with offline fixtures, explicit approval roles, and tracing/latency instrumentation for production monitoring.
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
