from typing import Any
import os
import json
from dotenv import load_dotenv
from models.state import GraphState
from langgraph.types import interrupt, Command

load_dotenv()
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")


def should_continue_testing(state: GraphState) -> str:
    """Router after testing — called after tester_node completes."""
    if state.get("tester_pending_command"):
        # Inner agent needs command approval — route to approval node
        return "tester_approval"
    elif state.get("tester_status") == "TESTS_PASSED":
        return "human_response"
    else:
        return "code"


def should_continue_after_approval(state: GraphState) -> str:
    """Router after tester_approval_node — always returns to tester_node to continue."""
    return "tester"


def extract_test_result(result) -> dict:
    """
    Extract test status and comments from the tester agent result.
    ONLY returns TESTS_PASSED if the structured output explicitly says test_status='PASS'.
    Text fallback defaults to TESTS_FAILED — safe default, agent should always return JSON.
    """
    # PRIMARY: use structured output (ProviderStrategy / TesterResult)
    if isinstance(result, dict) and "structured_response" in result:
        sr = result["structured_response"]
        if isinstance(sr, dict):
            test_status = sr.get("test_status", "")
            comments = sr.get("comments", "")
        else:
            test_status = getattr(sr, "test_status", "")
            comments = getattr(sr, "comments", "")

        status = "TESTS_PASSED" if str(test_status).upper() == "PASS" else "TESTS_FAILED"
        print(f"[Tester] Structured output: test_status='{test_status}' → {status}")
        return {"status": status, "comments": str(comments).strip()}

    # FALLBACK: no structured output — default TESTS_FAILED to force coder to retry
    if isinstance(result, dict) and result.get("messages"):
        msg = result["messages"][-1]
        content = msg.content
    elif hasattr(result, 'messages') and result.messages:
        content = result.messages[-1].content
    else:
        content = str(result)


    # Handle content blocks (list of dicts) common in recent models
    if isinstance(content, list):
        content = "\n".join([str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content])
    else:
        content = str(content)

    print(f"[Tester] WARNING: No structured output — defaulting TESTS_FAILED. Preview: {content[:200]}")
    return {"status": "TESTS_FAILED", "comments": f"[Tester returned no structured output]\n\n{content.strip()}"}



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


async def _get_inner_interrupt(tester_agent, inner_config):
    """Check if the inner tester agent has a pending interrupt. Returns (hitl_request, has_interrupt)."""
    try:
        inner_state = await tester_agent.aget_state(inner_config)
        if inner_state.next:
            if hasattr(inner_state, 'tasks') and inner_state.tasks:
                for task in inner_state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        return task.interrupts[0].value, True
    except Exception:
        pass
    return None, False


async def _invoke_fresh_start(tester_agent, workspace_path, state, config):
    """Helper to invoke the agent with the initial prompt."""
    return await tester_agent.ainvoke({
        "messages": [{
            "role": "user",
            "content": f"""
Test this implementation and provide detailed feedback for the coding agent.

⚠️ VERIFICATION PLAN:
Your FIRST response must be a clear "Verification Plan" (markdown). Outline setup steps, commands, and edge cases.

⚠️ CRITICAL — PATH RULES:
- For ls(), read_file(), write_file(): ALWAYS use VIRTUAL paths starting with "/"
  NEVER pass Windows absolute paths to these tools!

- For execute_command(): The root workspace is: {workspace_path}
  Use FULL ABSOLUTE paths for working_dir. Explore with ls("/") first.

⚠️ MANDATORY EXECUTION:
- You MUST run actual commands with execute_command to verify the code works.
- Do NOT just read files and assume they work. Static review alone = TESTS_FAILED.
- One command per response. Wait for the result before proceeding.
- If a command fails, record the error and move to the next check.

⚠️ NO PERSISTENT PROCESSES:
- Do NOT run persistent processes like `npm run preview` or `python main.py` (which don't exit).
- The test environment will hang if you do.
- Instead, build the project and verify building succeeded, or use a tool/script that exits.

CODE SUMMARY:
{state['code_summary']}
"""
        }]
    }, config)


async def tester_node(state: GraphState, tester_agent: Any, outer_config: dict = None):
    """Run the inner tester agent (or resume it with a user decision).

    This node ALWAYS returns without calling interrupt().
    State is therefore always properly persisted before any pause.

    outer_config: The LangGraph RunnableConfig passed to this node from the outer graph.
    Its callbacks are forwarded into inner_invoke_config so that inner tool events
    (on_tool_start/on_tool_end for execute_command) propagate through the outer
    astream_events and appear in the frontend terminal UI.
    """
    print("--- [Tester Node] STARTED ---")
    workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])
    inner_config = {"configurable": {"thread_id": f"tester-{state['title']}"}}

    # Merge outer callbacks so inner tool events propagate through astream_events
    inner_invoke_config = dict(inner_config)
    if outer_config and outer_config.get("callbacks"):
        inner_invoke_config["callbacks"] = outer_config["callbacks"]

    pending_command = state.get("tester_pending_command")
    user_decision = state.get("tester_user_decision")  # Set by tester_approval_node

    # Check if inner state exists (detect MemorySaver wipe/hot-reload)
    hitl_request, has_inner_interrupt = await _get_inner_interrupt(tester_agent, inner_config)

    if user_decision is not None:
        # ── CASE 1: RESUME (User provided a decision for a pending command) ────────
        if not has_inner_interrupt:
            print("[Tester] WARNING: Resume requested but inner state was wiped (hot-reload?)")
            print("[Tester] Gracefully falling back to fresh start.")
            result = await _invoke_fresh_start(tester_agent, workspace_path, state, inner_invoke_config)
        else:
            print(f"[Tester] Resume — forwarding decision '{user_decision}' to inner agent")
            num_actions = _count_action_requests(hitl_request)
            decision_type = "approve" if str(user_decision).lower().strip() in ("approve", "yes", "y") else "reject"
            decisions = [{"type": decision_type} for _ in range(num_actions)]
            print(f"[Tester] Sending {len(decisions)} x {decision_type} to inner agent")

            result = await tester_agent.ainvoke(
                Command(resume={"decisions": decisions}),
                inner_invoke_config,
            )

    elif not pending_command:
        # ── CASE 2: FRESH START (No pending command, no decision) ─────────────────
        print("[Tester] Fresh start — invoking inner agent")
        result = await _invoke_fresh_start(tester_agent, workspace_path, state, inner_invoke_config)

    else:
        # ── CASE 3: UNEXPECTED (Pending command exists but no user decision) ────────
        # This can happen if the graph resumed at tester_node instead of tester_approval_node.
        print("[Tester] WARNING: pending_command set but no user_decision. Defaulting to approve.")
        if not has_inner_interrupt:
            print("[Tester] Inner state wiped, falling back to fresh start.")
            result = await _invoke_fresh_start(tester_agent, workspace_path, state, inner_invoke_config)
        else:
            num_actions = _count_action_requests(hitl_request) if hitl_request else 1
            decisions = [{"type": "approve"} for _ in range(num_actions)]
            result = await tester_agent.ainvoke(
                Command(resume={"decisions": decisions}),
                inner_invoke_config,
            )

    # ── CHECK RESULT: does inner agent need another command approval? ────────────
    hitl_request, has_interrupt = await _get_inner_interrupt(tester_agent, inner_config)

    if has_interrupt and hitl_request is not None:

        # Inner agent is waiting for another command approval
        command_details = _format_action_requests(hitl_request)
        num_actions = _count_action_requests(hitl_request)
        print(f"[Tester] Inner agent needs approval: {command_details[:200]}")

        # Return with pending command — should_continue_testing will route to tester_approval
        return {
            "tester_pending_command": command_details,
            "tester_user_decision": None,  # Clear previous decision
            "agent_node": "tester"
        }

    # ── DONE: inner agent completed ──────────────────────────────────────────────
    test_result = extract_test_result(result)
    print("--- [Tester Node] COMPLETED ---")
    print(test_result["comments"][:3000])
    return {
        "tester_pending_command": None,
        "tester_user_decision": None,
        "tester_status": test_result["status"],
        "tester_comments": test_result["comments"],
        "agent_node": "tester"
    }


def tester_approval_node(state: GraphState):
    """Pause the graph to get user approval for a tester command.

    This node:
    1. Calls interrupt() to show the pending command to the user and wait for their decision.
    2. Returns the decision as tester_user_decision so tester_node can use it.
    NOTE: Does NOT clear tester_pending_command — tester_node needs it to read num_actions.

    After this node, should_continue_after_approval routes back to tester_node.
    """
    print("--- [Tester Approval Node] STARTED ---")
    command_details = state.get("tester_pending_command", "")

    user_decision = interrupt({
        "type": "command_approval",
        "instruction": f"🧪 **Tester wants to run a command:**\n\n{command_details}\n\nType **approve** to allow or **reject** to skip.",
        "content_to_review": command_details
    })

    print(f"--- [Tester Approval Node] User decision: {user_decision} ---")
    return {
        # Store decision for tester_node to read. Keep tester_pending_command intact!
        "tester_user_decision": user_decision,
        "agent_node": "tester"
    }
