from typing import Annotated, List, Optional, TypedDict, Dict, Literal, Any
import operator


class GraphState(TypedDict):
    """
    Single source of truth for the entire workflow.
    Every field that the frontend needs to render must live here.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    title: str
    thread_id: str  # was missing — LangGraph needs this persisted

    # ── Execution status (CRITICAL — fixes "UI stuck running" bug) ────────────
    # Set by each node on entry/exit so the frontend always knows where we are.
    status: Literal["idle", "running", "waiting", "completed", "error"]
    current_node: Optional[str]  # e.g. "coder_agent", "validation_agent"

    # ── Human-in-the-loop ─────────────────────────────────────────────────────
    agent_node: str        # legacy field — keep for now, frontend reads it
    user_response: str

    # ── Architect phase ───────────────────────────────────────────────────────
    architect_response: str
    final_architect_response: str
    # Annotated[list, operator.add] = append-only — each loop adds new messages
    # without overwriting old ones, which is what we want for conversation memory
    architect_messages: Annotated[list, operator.add]

    # ── Planner phase ─────────────────────────────────────────────────────────
    planner_response: str
    final_planner_response: str
    planner_messages: Annotated[list, operator.add]

    # ── Coder phase ───────────────────────────────────────────────────────────
    code_summary: str
    # Persisted todo list so the UI can restore it on page refresh.
    # Each item: {"task": str, "status": "pending"|"in_progress"|"completed"}
    todos: List[Dict[str, Any]]

    # ── Validation phase ──────────────────────────────────────────────────────
    validation_status: str
    validation_comments: str
    validation_pending_command: Optional[str]
    validation_user_decision: Optional[str]
    validation_approval_count: int  # Tracks command approval loops to prevent infinite retries

    # ── Summarizer phase ──────────────────────────────────────────────────────
    final_summary: str

    # ── Errors ────────────────────────────────────────────────────────────────
    errors: List[str]

