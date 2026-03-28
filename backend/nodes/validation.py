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

# Maximum number of command approval cycles before force-failing validation
MAX_APPROVAL_RETRIES = 5


def should_continue_coding(state: GraphState) -> str:
    """Router after validation — called after validation_node completes."""
    if state.get("validation_pending_command"):
        # Inner agent needs command approval — route to approval node
        return "validation_approval"
    elif state.get("validation_status", "") == "VALIDATION_COMPLETE":
        # Exact match — only route to summarizer when validation fully passed
        return "summarize"
    else:
        # VALIDATION_INCOMPLETE or any other status → back to coder for fixes
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
    # Use exact status match — avoid substring issues
    # (e.g., "validation_incomplete" must NOT match as "complete")
    if '"status": "validation_complete"' in content_lower or '"status":"validation_complete"' in content_lower or 'validation_passed' in content_lower:
        status = "VALIDATION_COMPLETE"
    else:
        status = "VALIDATION_INCOMPLETE"
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

════════════════════════════════════════════════
⛔ MANDATORY: TWO-PHASE VALIDATION
════════════════════════════════════════════════

PHASE 1 — CODE REVIEW (READ-ONLY):
You must complete ALL of these checks using ONLY ls() and read_file().
⛔ DO NOT call execute_command() during Phase 1.

1. STRUCTURE: Use ls("/") to verify all expected files/directories exist

2. GOAL COMPLETENESS — THIS IS YOUR MOST IMPORTANT CHECK:
   You MUST read_file() on EVERY source file (not just a few).
   For EACH goal in the original plan, find the file(s) that implement it and verify:
   - The feature has REAL, WORKING code (not a stub)
   - The component/function actually DOES something
   
   ⛔ THESE ARE ALL FAILURES — flag them as MISSING/INCOMPLETE:
   - A file that just says: <h1>Title</h1> with a comment like "Add components here"
   - A function body that is just `pass` or `return None` or `// TODO`
   - A component that renders only a heading with no actual UI/logic
   - A route handler that returns a hardcoded dummy response
   - An empty class with no methods implemented
   - Any placeholder text like "Coming soon", "TODO", "Add your code here"
   
   If the plan says "build a feed page with posts" and the code is just
   `<div><h1>Feed</h1></div>` — that is INCOMPLETE. Flag it.

3. IMPORTS: Check every import references a real package, no deprecated imports,
   internal imports point to files that exist

4. CODE LOGIC: Verify functions have real logic (not empty/pass), no obvious bugs,
   CRUD operations are complete, UI wires to backend properly

5. SYNTAX: Check for missing brackets, colons, quotes, indentation errors

6. DEPENDENCY FILES: Verify requirements.txt / package.json exists and lists
   all packages that are actually imported in the code

If ANY issue is found in Phase 1:
→ Write validation_summary.md with sections: MISSING/INCOMPLETE FEATURES,
  IMPORT ERRORS, CODE LOGIC ERRORS, SYNTAX ERRORS, MISSING FILES
→ Return VALIDATION_INCOMPLETE immediately. Do NOT proceed to Phase 2.

PHASE 2 — RUNTIME VALIDATION (only if Phase 1 has ZERO issues):
NOW you may use execute_command().

⚠️ BEFORE running ANY command:
1. Use read_file("/PROJECT_SUMMARY.md") to find the EXACT commands and EXACT directories
2. Only run commands you are 100% certain are correct, in the correct directory
3. If you are NOT 100% sure about a command or directory → skip it and note in summary

Steps:
1. Install deps — use the EXACT command and directory from PROJECT_SUMMARY.md
   (e.g., npm install in the directory where package.json exists)
2. Build/compile (npm run build / python -m py_compile) in the CORRECT directory
3. Smoke test — run the app briefly, check for runtime errors

⛔ DO NOT use: docker, docker-compose, docker build, kubectl, terraform
   These are not available in this environment.

Code bug in Phase 2 → VALIDATION_INCOMPLETE (send back to coder)
Missing foreign/external package (system-level dependency, unavailable package) 
  → This is NOT the coder's fault → VALIDATION_COMPLETE with detailed user instructions
External setup issue (API keys, DB) → VALIDATION_COMPLETE with notes

Be thorough — READ THE ACTUAL CODE, don't just rely on the summary!
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
    approval_count = state.get("validation_approval_count", 0)

    # ── RETRY GUARD: Prevent infinite approval loops ──────────────────────────
    if approval_count >= MAX_APPROVAL_RETRIES:
        print(f"[Validation] ⛔ Hit max approval retries ({MAX_APPROVAL_RETRIES}). Force-failing validation.")
        return {
            "validation_pending_command": None,
            "validation_user_decision": None,
            "validation_approval_count": approval_count,
            "validation_status": "VALIDATION_INCOMPLETE",
            "validation_comments": (
                f"Validation aborted: The validation agent requested command approval "
                f"{approval_count} times without completing. This usually means the agent "
                f"is stuck in a loop (e.g., trying to install a missing requirements.txt). "
                f"The coder agent should fix the underlying issues before re-validation."
            ),
            "agent_node": "validation_agent"
        }

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
        new_approval_count = approval_count + 1
        print(f"[Validation] Inner agent needs approval ({new_approval_count}/{MAX_APPROVAL_RETRIES}): {command_details[:200]}")

        # Return with pending command — should_continue_coding will route to validation_approval
        return {
            "validation_pending_command": command_details,
            "validation_user_decision": None,  # Clear previous decision
            "validation_approval_count": new_approval_count,
            "agent_node": "validation_agent"
        }

    # ── DONE: inner agent completed ───────────────────────────────────────────
    validation_result = extract_validation_result(result)
    print("--- [Validation Node] COMPLETED ---")
    print(validation_result["comments"][:3000])
    return {
        "validation_pending_command": None,
        "validation_user_decision": None,
        "validation_approval_count": 0,  # Reset for next validation cycle
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
    approval_count = state.get("validation_approval_count", 0)

    user_decision = interrupt({
        "type": "command_approval",
        "instruction": f"🔍 **Validator wants to run a command ({approval_count}/{MAX_APPROVAL_RETRIES}):**\n\n{command_details}\n\nType **approve** to allow or **reject** to skip.",
        "content_to_review": command_details
    })

    print(f"--- [Validation Approval Node] User decision: {user_decision} ---")
    return {
        # Store decision for validation_node to read. Keep validation_pending_command intact!
        "validation_user_decision": user_decision,
        "agent_node": "validation_agent"
    }
