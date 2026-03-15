from typing import Any
from models.state import GraphState
import os
import json
from dotenv import load_dotenv
from tools.validation import execute_command
from langgraph.types import interrupt, Command

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL")
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")


def should_continue_coding(state: GraphState) -> str:
    """Router after validation — called after validation_node completes."""
    if state.get("validation_pending_command"):
        # Inner agent needs command approval — route to approval node
        return "validation_approval"
    elif "COMPLETE" in state.get("validation_status", ""):
        return "summarize"
    else:
        return "code"


def should_continue_after_validation_approval(state: GraphState) -> str:
    """Router after validation_approval_node — always returns to validation_node to continue."""
    return "validation"




# ── Result extraction ─────────────────────────────────────────────────────────

def extract_validation_result(result) -> dict:
    """
    Extract validation status and comments from the validation agent result.
    Uses structured output (ValidationResult) if available, falls back to text.
    """
    # PRIMARY: structured output from ProviderStrategy(ValidationResult)
    if isinstance(result, dict) and "structured_response" in result:
        sr = result["structured_response"]
        if isinstance(sr, dict):
            test_status = sr.get("test_status", "")
            comments = sr.get("comments", "")
        else:
            test_status = getattr(sr, "test_status", "")
            comments = getattr(sr, "comments", "")

        status = "VALIDATION_COMPLETE" if str(test_status).upper() in ("VALIDATION_COMPLETE", "PASS", "COMPLETE") else "VALIDATION_INCOMPLETE"
        print(f"[Validation] Structured output: test_status='{test_status}' → {status}")
        return {"status": status, "comments": str(comments).strip()}

    # FALLBACK: extract from last message
    if isinstance(result, dict) and result.get("messages"):
        content = result["messages"][-1].content
    elif hasattr(result, "messages") and result.messages:
        content = result.messages[-1].content
    else:
        content = str(result)

    if isinstance(content, list):
        content = "\n".join([str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content])
    else:
        content = str(content)

    content_lower = content.lower()
    status = "VALIDATION_COMPLETE" if "validation_complete" in content_lower or "validation_passed" in content_lower else "VALIDATION_INCOMPLETE"
    print(f"[Validation] WARNING: No structured output — defaulting to text parse: {status}")
    return {"status": status, "comments": content.strip()}


def _format_action_requests(hitl_request) -> str:
    """Format HITLRequest action_requests into readable command descriptions."""
    lines = []
    action_requests = hitl_request.get("action_requests", []) if isinstance(hitl_request, dict) else getattr(hitl_request, "action_requests", [])

    for i, req in enumerate(action_requests, 1):
        name = req.get("name", "unknown") if isinstance(req, dict) else getattr(req, "name", "unknown")
        args = req.get("args", {}) if isinstance(req, dict) else getattr(req, "args", {})

        if name == "execute_command":
            cmd = args.get("command", "")
            wdir = args.get("working_dir", "")
            lines.append(f"**Command {i}:** `{cmd}`")
            if wdir:
                lines.append(f"  Working dir: `{wdir}`")
        else:
            lines.append(f"**Tool {i}:** `{name}({json.dumps(args, default=str)})`")

    return "\n".join(lines) if lines else f"```\n{json.dumps(str(hitl_request), indent=2, default=str)}\n```"


def _count_action_requests(hitl_request) -> int:
    """Count how many action_requests are in the HITLRequest."""
    action_requests = hitl_request.get("action_requests", []) if isinstance(hitl_request, dict) else getattr(hitl_request, "action_requests", [])
    return len(action_requests)


async def _get_inner_interrupt(validation_agent, inner_config):
    """Check if the inner validation agent has a pending interrupt. Returns (hitl_request, has_interrupt)."""
    try:
        inner_state = await validation_agent.aget_state(inner_config)
        if inner_state.next:
            if hasattr(inner_state, "tasks") and inner_state.tasks:
                for task in inner_state.tasks:
                    if hasattr(task, "interrupts") and task.interrupts:
                        return task.interrupts[0].value, True
    except Exception:
        pass
    return None, False


async def _invoke_fresh_validation(validation_agent, workspace_path, state, config):
    """Helper to invoke the validation agent with the initial prompt."""
    return await validation_agent.ainvoke({
        "messages": [{
            "role": "user",
            "content": f"""
You are validating a code implementation against the original plan.

ORIGINAL PLAN:
{state['planner_response']}

CODE SUMMARY FROM CODING AGENT:
{state['code_summary']}

⚠️ CRITICAL — PATH RULES:
- For ls(), read_file(), write_file(): ALWAYS use VIRTUAL paths starting with "/"
  NEVER pass Windows absolute paths to these tools!

- For execute_command(): The root workspace is: {workspace_path}
  Use FULL ABSOLUTE paths for working_dir. Explore with ls("/") first.

YOUR VALIDATION PROCESS (do ALL steps yourself):
1. STRUCTURE: Use ls("/") to verify all expected files exist
2. PLAN: Use read_file() to read code and verify it matches the plan
3. SYNTAX: Check for syntax errors, use execute_command if needed
4. ENVIRONMENT: Set up environment (npm install / pip install), use execute_command
5. RUNTIME: Run the application using execute_command, check for errors
6. Write validation_summary.md with results from all steps
7. Return final result as JSON with status and comments

Be thorough - READ THE ACTUAL CODE AND RUN IT, don't just rely on the summary!
"""
        }]
    }, config)


# ── Main validation node ──────────────────────────────────────────────────────

async def validation_node(state: GraphState, validation_agent: Any, outer_config: dict = None):
    """Run the inner validation agent (or resume it with a user decision).

    This node ALWAYS returns without calling interrupt().
    State is therefore always properly persisted before any pause.

    outer_config: The LangGraph RunnableConfig passed to this node from the outer graph.
    Its callbacks are forwarded into inner_invoke_config so that inner tool events
    (on_tool_start/on_tool_end for execute_command) propagate through the outer
    astream_events and appear in the frontend terminal UI.
    """
    print("--- [Validation Node] STARTED ---")
    workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])
    inner_config = {"configurable": {"thread_id": f"validation-{state['title']}"}}

    # Merge outer callbacks so inner tool events propagate through astream_events
    inner_invoke_config = dict(inner_config)
    if outer_config and outer_config.get("callbacks"):
        inner_invoke_config["callbacks"] = outer_config["callbacks"]

    pending_command = state.get("validation_pending_command")
    user_decision = state.get("validation_user_decision")  # Set by validation_approval_node

    # Check if inner state exists (detect MemorySaver wipe/hot-reload)
    hitl_request, has_inner_interrupt = await _get_inner_interrupt(validation_agent, inner_config)

    if user_decision is not None:
        # ── CASE 1: RESUME (User provided a decision for a pending command) ─────
        if not has_inner_interrupt:
            print("[Validation] WARNING: Resume requested but inner state was wiped (hot-reload?)")
            print("[Validation] Gracefully falling back to fresh validation.")
            result = await _invoke_fresh_validation(validation_agent, workspace_path, state, inner_invoke_config)
        else:
            print(f"[Validation] Resume — forwarding decision '{user_decision}' to inner agent")
            num_actions = _count_action_requests(hitl_request)
            decision_type = "approve" if str(user_decision).lower().strip() in ("approve", "yes", "y") else "reject"
            decisions = [{"type": decision_type} for _ in range(num_actions)]
            print(f"[Validation] Sending {len(decisions)} x {decision_type} to inner agent")

            result = await validation_agent.ainvoke(
                Command(resume={"decisions": decisions}),
                inner_invoke_config,
            )

    elif not pending_command:
        # ── CASE 2: FRESH START ──────────────────────────────────────────────
        print("[Validation] Fresh start — invoking inner agent")
        result = await _invoke_fresh_validation(validation_agent, workspace_path, state, inner_invoke_config)

    else:
        # ── CASE 3: UNEXPECTED: pending command but no decision ──────────────
        print("[Validation] WARNING: pending_command set but no user_decision. Defaulting to approve.")
        if not has_inner_interrupt:
            print("[Validation] Inner state wiped, falling back to fresh validation.")
            result = await _invoke_fresh_validation(validation_agent, workspace_path, state, inner_invoke_config)
        else:
            num_actions = _count_action_requests(hitl_request) if hitl_request else 1
            decisions = [{"type": "approve"} for _ in range(num_actions)]
            result = await validation_agent.ainvoke(
                Command(resume={"decisions": decisions}),
                inner_invoke_config,
            )

    # ── CHECK RESULT: does inner agent need another command approval? ─────────
    hitl_request, has_interrupt = await _get_inner_interrupt(validation_agent, inner_config)

    if has_interrupt and hitl_request is not None:
        # Inner agent is waiting for another command approval
        command_details = _format_action_requests(hitl_request)
        num_actions = _count_action_requests(hitl_request)
        print(f"[Validation] Inner agent needs approval: {command_details[:200]}")

        # Return with pending command — should_continue_coding will route to validation_approval
        return {
            "validation_pending_command": command_details,
            "validation_user_decision": None,  # Clear previous decision
            "agent_node": "validation_agent"
        }

    # ── DONE: inner agent completed ───────────────────────────────────────────
    validation_result = extract_validation_result(result)
    print("--- [Validation Node] COMPLETED ---")
    print(validation_result["comments"][:3000])
    return {
        "validation_pending_command": None,
        "validation_user_decision": None,
        "validation_status": validation_result["status"],
        "validation_comments": validation_result["comments"],
        "agent_node": "validation_agent"
    }


# ── Validation approval node ──────────────────────────────────────────────────

def validation_approval_node(state: GraphState):
    """Pause the graph to get user approval for a validation command.

    This node:
    1. Calls interrupt() to show the pending command to the user and wait for their decision.
    2. Returns the decision as validation_user_decision so validation_node can use it.
    NOTE: Does NOT clear validation_pending_command — validation_node needs it to read num_actions.

    After this node, should_continue_after_validation_approval routes back to validation_node.
    """
    print("--- [Validation Approval Node] STARTED ---")
    command_details = state.get("validation_pending_command", "")

    user_decision = interrupt({
        "type": "command_approval",
        "instruction": f"🔍 **Validator wants to run a command:**\n\n{command_details}\n\nType **approve** to allow or **reject** to skip.",
        "content_to_review": command_details
    })

    print(f"--- [Validation Approval Node] User decision: {user_decision} ---")
    return {
        # Store decision for validation_node to read. Keep validation_pending_command intact!
        "validation_user_decision": user_decision,
        "agent_node": "validation_agent"
    }
