"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, make_event


class IntentClassification(BaseModel):
    """Schema enforced by the classifier's structured LLM output."""

    route: Literal["simple", "tool", "missing_info", "risky", "error"]
    rationale: str = Field(description="Short explanation of the selected route")


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── TODO(student): implement ALL nodes below ────────────────────────


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM.

    *** MUST use a real LLM call — keyword-only heuristics will lose points. ***

    Use .with_structured_output() or equivalent to get reliable enum classification.
    The LLM should classify into one of: simple, tool, missing_info, risky, error.

    Hints:
    - See llm.py for the get_llm() helper
    - Use Pydantic model or TypedDict with .with_structured_output()
    - Set risk_level to "high" for risky routes, "low" otherwise
    - Priority guide: risky > tool > missing_info > error > simple

    Return: {"route": str, "risk_level": str, "events": [make_event(...)]}
    """
    prompt = """You triage customer-support tickets. Classify the request into exactly one route.

Routes, in priority order when more than one could apply:
1. risky: any request with side effects (refund, delete, cancel, send email, change account).
2. tool: a request to retrieve or look up information (order, shipment, account status).
3. missing_info: too vague to act on; it has no identifiable issue, object, or desired outcome.
4. error: reports a system failure such as timeout, crash, unavailable service, or exception.
5. simple: general support question answerable without a lookup or action.

Return the route and a concise rationale. Do not infer actions that are not in the ticket.

Ticket: {query}""".format(query=state.get("query", ""))
    structured_llm = get_llm().with_structured_output(IntentClassification)
    classification = structured_llm.invoke(prompt)
    return {
        "route": classification.route,
        "risk_level": "high" if classification.route == "risky" else "low",
        "events": [
            make_event(
                "classify",
                "completed",
                "intent classified by structured LLM output",
                route=classification.route,
                rationale=classification.rationale,
            )
        ],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.

    Simulate transient failures for error-route scenarios to test retry loops.

    Requirements:
    - Read current attempt count from state
    - If route is "error" and attempt < 2: return error result (string containing "ERROR")
    - Otherwise: return a mock success result string
    - Append result to tool_results list

    Return: {"tool_results": [result_string], "events": [make_event(...)]}
    """
    attempt = int(state.get("attempt", 0))
    route = state.get("route", "")
    should_fail = route == "error" and attempt < 2
    if should_fail:
        result = f"ERROR: transient service timeout on attempt {attempt + 1}"
        event_type = "failed"
    else:
        action = state.get("proposed_action") or "support lookup"
        result = f"SUCCESS: mock tool completed {action} on attempt {attempt + 1}."
        event_type = "completed"
    return {
        "tool_results": [result],
        "events": [make_event("tool", event_type, result, attempt=attempt)],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate.

    Check whether the latest tool result is satisfactory or needs retry.

    SHOULD use LLM-as-judge for bonus points. Heuristic (e.g., check for "ERROR" substring)
    is acceptable for base score.

    Requirements:
    - Read the latest entry from tool_results
    - Set evaluation_result to "needs_retry" or "success"
    - This field drives route_after_evaluate conditional edge

    Note: You may need to add 'evaluation_result' to AgentState if not present.

    Return: {"evaluation_result": str, "events": [make_event(...)]}
    """
    latest_result = (state.get("tool_results") or [""])[-1]
    evaluation = "needs_retry" if "ERROR" in latest_result.upper() else "success"
    return {
        "evaluation_result": evaluation,
        "events": [
            make_event("evaluate", "completed", f"tool result evaluated as {evaluation}")
        ],
    }


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM.

    *** MUST use a real LLM call — hardcoded strings will lose points. ***

    The LLM should generate a helpful response grounded in available context:
    - tool_results (if any)
    - approval decision (if risky route)
    - original query

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    context = "\n".join(state.get("tool_results") or []) or "No tool result was needed."
    approval = state.get("approval")
    prompt = """You are a careful customer-support agent. Write a concise, helpful final response.
Only state facts supported by the context. Do not claim an action was performed unless the
tool context explicitly says SUCCESS. If approval is present, state that it was reviewed.

Customer query: {query}
Route: {route}
Tool context: {context}
Approval: {approval}
""".format(
        query=state.get("query", ""),
        route=state.get("route", "simple"),
        context=context,
        approval=approval or "not required",
    )
    response = get_llm().invoke(prompt)
    answer = getattr(response, "content", str(response)).strip()
    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "grounded answer generated by LLM")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.

    Generate a specific clarification question based on the vague/incomplete query.

    Note: You may need to add 'pending_question' to AgentState if not present.

    Return: {"pending_question": str, "final_answer": str, "events": [make_event(...)]}
    """
    question = (
        "Could you share the affected account, order, or service and describe the outcome "
        "you want? That will let me investigate safely."
    )
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "requested missing context")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval.

    Describe the proposed action and why it requires approval.

    Note: You may need to add 'proposed_action' to AgentState if not present.

    Return: {"proposed_action": str, "events": [make_event(...)]}
    """
    action = f"Proposed side-effecting action for request: {state.get('query', '')}"
    return {
        "proposed_action": action,
        "events": [make_event("risky_action", "pending_approval", action)],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Default behavior: mock approval (approved=True) so tests and CI run offline.
    Extension: if env LANGGRAPH_INTERRUPT=true, use langgraph.types.interrupt() for real HITL.

    Return: {"approval": {"approved": bool, "reviewer": str, "comment": str}, "events": [make_event(...)]}
    """
    if os.getenv("LANGGRAPH_INTERRUPT", "false").lower() == "true":
        from langgraph.types import interrupt

        decision = interrupt(
            {"action": state.get("proposed_action"), "message": "Approve this action?"}
        )
        approved = bool(decision.get("approved", False)) if isinstance(decision, dict) else bool(decision)
        reviewer = "human-reviewer"
        comment = "Decision supplied through LangGraph interrupt."
    else:
        approved = True
        reviewer = "mock-reviewer"
        comment = "Auto-approved for deterministic offline CI."
    approval = {"approved": approved, "reviewer": reviewer, "comment": comment}
    return {
        "approval": approval,
        "events": [make_event("approval", "completed", "approval decision recorded", **approval)],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt.

    Increment the attempt counter and log the transient failure.

    Requirements:
    - Read current attempt from state, increment by 1
    - Add an error message to errors list
    - Return updated attempt count

    Return: {"attempt": int, "errors": [str], "events": [make_event(...)]}
    """
    attempt = int(state.get("attempt", 0)) + 1
    message = f"Retry attempt {attempt} recorded after a transient tool failure."
    return {
        "attempt": attempt,
        "errors": [message],
        "events": [make_event("retry", "scheduled", message, attempt=attempt)],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded.

    This is the third layer: retry → fallback → dead letter.
    Log the failure and set a final_answer explaining that the request could not be completed.

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    answer = (
        "I could not complete this request after the configured retry limit. "
        "The incident has been recorded for human support follow-up."
    )
    return {
        "final_answer": answer,
        "errors": ["Request moved to dead letter after retry limit."],
        "events": [make_event("dead_letter", "escalated", "retry limit exhausted")],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END.

    Return: {"events": [make_event("finalize", "completed", "workflow finished")]}
    """
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
