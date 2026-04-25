from typing import Any
from models.state import GraphState
from models.project_context import ProjectContext
import os
import json
import time
from dotenv import load_dotenv
from tools.validation import execute_command
from langgraph.types import interrupt, Command

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL")
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")

MAX_APPROVAL_RETRIES = 5
MAX_CODING_RETRIES = 3  # must match orchestrator.py


# ── Routing ───────────────────────────────────────────────────────────────────

def should_continue_coding(state: GraphState) -> str:
    if state.get("validation_pending_command"):
        return "validation_approval"
    elif state.get("validation_status", "") == "VALIDATION_COMPLETE":
        return "summarize"
    else:
        # Check retry guard before sending back to coder
        if state.get("coding_retry_count", 0) >= MAX_CODING_RETRIES:
            print(f"[Validation Router] Hit MAX_CODING_RETRIES. Forcing summarize.")
            return "summarize"
        return "code"


def should_continue_after_validation_approval(state: GraphState) -> str:
    return "validation"


# ── Result extraction ─────────────────────────────────────────────────────────

def extract_validation_result(result) -> dict:
    if isinstance(result, dict) and "structured_response" in result:
        sr = result["structured_response"]
        if isinstance(sr, dict):
            test_status = sr.get("test_status", "")
            comments = sr.get("comments", "")
        else:
            test_status = getattr(sr, "test_status", "")
            comments = getattr(sr, "comments", "")

        status = (
            "VALIDATION_COMPLETE"
            if str(test_status).upper() in ("VALIDATION_COMPLETE", "PASS", "COMPLETE")
            else "VALIDATION_INCOMPLETE"
        )
        print(f"[Validation] Structured output: test_status='{test_status}' → {status}")
        return {"status": status, "comments": str(comments).strip()}

    if isinstance(result, dict) and result.get("messages"):
        content = result["messages"][-1].content
    elif hasattr(result, "messages") and result.messages:
        content = result.messages[-1].content
    else:
        content = str(result)

    if isinstance(content, list):
        content = "\n".join(
            [str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content]
        )
    else:
        content = str(content)

    content_lower = content.lower()
    if (
        '"status": "validation_complete"' in content_lower
        or '"status":"validation_complete"' in content_lower
        or "validation_passed" in content_lower
    ):
        status = "VALIDATION_COMPLETE"
    else:
        status = "VALIDATION_INCOMPLETE"
    print(f"[Validation] WARNING: No structured output — text parse: {status}")
    return {"status": status, "comments": content.strip()}


def _extract_failed_files(comments: str) -> list:
    """
    Parse validation comments to extract specific files that need fixing.
    Looks for file paths mentioned in MISSING/INCOMPLETE FEATURES section.
    Returns a list of virtual paths like ["/backend/routers/auth.py", ...]
    """
    import re
    # Match lines that look like file paths: /something/something.py or .tsx
    paths = re.findall(r"(/[\w/\-\.]+\.(?:py|ts|tsx|js|jsx|json|txt))", comments)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result if result else []


def _format_action_requests(hitl_request) -> str:
    lines = []
    action_requests = (
        hitl_request.get("action_requests", [])
        if isinstance(hitl_request, dict)
        else getattr(hitl_request, "action_requests", [])
    )
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
    action_requests = (
        hitl_request.get("action_requests", [])
        if isinstance(hitl_request, dict)
        else getattr(hitl_request, "action_requests", [])
    )
    return len(action_requests)


async def _get_inner_interrupt(validation_agent, inner_config):
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


def _build_validation_prompt(state: GraphState, workspace_path: str) -> str:
    """
    Build the validation prompt with REAL disk paths injected.
    This is the fix for the /backend does not exist bug.
    """
    ctx = ProjectContext.load(workspace_path)

    # Real absolute paths for execute_command
    backend_real_path = os.path.join(workspace_path, "backend")
    frontend_real_path = os.path.join(workspace_path, "frontend")

    # Verify they exist — tell the validator upfront
    backend_exists = os.path.isdir(backend_real_path)
    frontend_exists = os.path.isdir(frontend_real_path)

    path_block = f"""
⚠️ REAL DISK PATHS — USE THESE IN execute_command(), NOT VIRTUAL PATHS:
  Workspace root: {workspace_path}
  Backend dir:    {backend_real_path}  (exists: {backend_exists})
  Frontend dir:   {frontend_real_path}  (exists: {frontend_exists})

CRITICAL PATH RULES:
  - For ls(), read_file(), write_file(): use VIRTUAL paths starting with "/"
    e.g. read_file("/backend/main.py") ✓
  - For execute_command() working_dir: use REAL ABSOLUTE paths above
    e.g. working_dir="{backend_real_path}" ✓  (NOT "/backend" ✗)
  - If execute_command returns "directory does not exist":
    → DO NOT retry the same command
    → Call read_file("/PROJECT_SUMMARY.md") to find correct paths
    → Then retry with the correct path found in that file
"""

    versions_block = ""
    if ctx:
        versions_text = "\n".join(f"  {k}: {v}" for k, v in ctx.pinned_versions.items())
        versions_block = f"""
EXPECTED PACKAGE VERSIONS (from project plan):
{versions_text}
"""

    return f"""You are validating a code implementation against the original plan.

ORIGINAL PLAN:
{state['planner_response']}

CODE SUMMARY FROM CODING AGENT:
{state['code_summary']}

{path_block}
{versions_block}

════════════════════════════════════════════════
⛔ MANDATORY: TWO-PHASE VALIDATION
════════════════════════════════════════════════

PHASE 1 — CODE REVIEW (READ-ONLY):
Use ONLY ls() and read_file(). ⛔ DO NOT call execute_command() during Phase 1.

1. STRUCTURE: Use ls("/") to verify all expected files/directories exist.

2. GOAL COMPLETENESS — MOST IMPORTANT:
   Read EVERY source file. For each goal in the plan, verify:
   - REAL, WORKING code (not a stub)
   - ⛔ FAILURES: "pass", "TODO", empty functions, placeholder text,
     <h1>Title</h1> with no actual UI, route handlers returning dummy responses.

3. IMPORTS: Check every import references a real package. Internal imports
   reference files that actually exist.

4. CODE LOGIC: Real logic in functions, complete CRUD, UI wired to backend.

5. DEPENDENCY FILES: requirements.txt and package.json list correct packages
   with the pinned versions from the EXPECTED PACKAGE VERSIONS block above.
   If versions differ → flag as IMPORT ERROR.

If ANY issue found in Phase 1:
→ Write validation_summary.md (sections: MISSING/INCOMPLETE FEATURES,
  IMPORT ERRORS, CODE LOGIC ERRORS, SYNTAX ERRORS, MISSING FILES)
→ In MISSING/INCOMPLETE FEATURES, always include the EXACT FILE PATH
  of each file that has the issue (e.g. "/backend/routers/auth.py").
→ Return VALIDATION_INCOMPLETE immediately. Do NOT proceed to Phase 2.

PHASE 2 — RUNTIME VALIDATION (only if Phase 1 has ZERO issues):
NOW you may use execute_command(). ALWAYS use the REAL disk paths above.

Steps:
1. read_file("/PROJECT_SUMMARY.md") to get exact commands and directories.
2. Install deps:
   - Python: pip install -r requirements.txt
     working_dir="{backend_real_path}"
   - Node: npm install
     working_dir="{frontend_real_path}"
3. Build/compile:
   - Python: python -m py_compile main.py
     working_dir="{backend_real_path}"
   - Node: npx tsc --noEmit
     working_dir="{frontend_real_path}"
4. Report results.

⛔ If execute_command returns "directory does not exist":
   → STOP. Do NOT retry.
   → Read /PROJECT_SUMMARY.md and find the correct directory.
   → Retry with the correct directory exactly once.
   → If it still fails, mark as VALIDATION_COMPLETE with setup instructions.

⛔ DO NOT use: docker, docker-compose, kubectl, terraform.

OUTPUT FORMAT (final response only):
{{
 "status": "VALIDATION_COMPLETE" or "VALIDATION_INCOMPLETE",
 "comments": "Detailed summary of everything. Include exact file paths for all issues."
}}
"""


async def _invoke_fresh_validation(validation_agent, workspace_path, state, config):
    prompt = _build_validation_prompt(state, workspace_path)
    return await validation_agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config,
    )


# ── Main validation node ──────────────────────────────────────────────────────

async def validation_node(state: GraphState, validation_agent: Any, outer_config: dict = None):
    t_start = time.time()
    print("--- [Validation Node] STARTED ---")
    workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])
    inner_config = {"configurable": {"thread_id": f"validation-{state['title']}"}}

    inner_invoke_config = dict(inner_config)
    if outer_config and outer_config.get("callbacks"):
        inner_invoke_config["callbacks"] = outer_config["callbacks"]

    pending_command = state.get("validation_pending_command")
    user_decision = state.get("validation_user_decision")
    approval_count = state.get("validation_approval_count", 0)

    # ── RETRY GUARD ───────────────────────────────────────────────────────────
    if approval_count >= MAX_APPROVAL_RETRIES:
        print(f"[Validation] ⛔ Hit max approval retries ({MAX_APPROVAL_RETRIES}).")
        elapsed = time.time() - t_start
        timings = dict(state.get("node_timings", {}))
        timings["validation_agent"] = elapsed
        return {
            "validation_pending_command": None,
            "validation_user_decision": None,
            "validation_approval_count": approval_count,
            "validation_status": "VALIDATION_INCOMPLETE",
            "validation_comments": (
                f"Validation aborted: agent requested command approval "
                f"{approval_count} times without completing. "
                f"The coder agent should fix the underlying issues before re-validation."
            ),
            "validation_failed_files": [],
            "agent_node": "validation_agent",
            "node_timings": timings,
        }

    hitl_request, has_inner_interrupt = await _get_inner_interrupt(validation_agent, inner_config)

    if user_decision is not None:
        if not has_inner_interrupt:
            print("[Validation] WARNING: Resume requested but inner state wiped. Fresh start.")
            result = await _invoke_fresh_validation(validation_agent, workspace_path, state, inner_invoke_config)
        else:
            print(f"[Validation] Resume — forwarding decision '{user_decision}'")
            num_actions = _count_action_requests(hitl_request)
            decision_type = "approve" if str(user_decision).lower().strip() in ("approve", "yes", "y") else "reject"
            decisions = [{"type": decision_type} for _ in range(num_actions)]
            result = await validation_agent.ainvoke(
                Command(resume={"decisions": decisions}),
                inner_invoke_config,
            )
    elif not pending_command:
        print("[Validation] Fresh start — invoking inner agent")
        result = await _invoke_fresh_validation(validation_agent, workspace_path, state, inner_invoke_config)
    else:
        print("[Validation] WARNING: pending_command set but no decision. Defaulting to approve.")
        if not has_inner_interrupt:
            result = await _invoke_fresh_validation(validation_agent, workspace_path, state, inner_invoke_config)
        else:
            num_actions = _count_action_requests(hitl_request) if hitl_request else 1
            decisions = [{"type": "approve"} for _ in range(num_actions)]
            result = await validation_agent.ainvoke(
                Command(resume={"decisions": decisions}),
                inner_invoke_config,
            )

    hitl_request, has_interrupt = await _get_inner_interrupt(validation_agent, inner_config)

    if has_interrupt and hitl_request is not None:
        command_details = _format_action_requests(hitl_request)
        num_actions = _count_action_requests(hitl_request)
        new_approval_count = approval_count + 1
        print(f"[Validation] Inner agent needs approval ({new_approval_count}/{MAX_APPROVAL_RETRIES})")
        elapsed = time.time() - t_start
        timings = dict(state.get("node_timings", {}))
        timings["validation_agent"] = elapsed
        return {
            "validation_pending_command": command_details,
            "validation_user_decision": None,
            "validation_approval_count": new_approval_count,
            "agent_node": "validation_agent",
            "node_timings": timings,
        }

    validation_result = extract_validation_result(result)
    failed_files = _extract_failed_files(validation_result["comments"])

    elapsed = time.time() - t_start
    print(f"--- [Validation Node] COMPLETED in {elapsed:.1f}s ---")
    print(validation_result["comments"][:3000])

    timings = dict(state.get("node_timings", {}))
    timings["validation_agent"] = elapsed

    return {
        "validation_pending_command": None,
        "validation_user_decision": None,
        "validation_approval_count": 0,
        "validation_status": validation_result["status"],
        "validation_comments": validation_result["comments"],
        "validation_failed_files": failed_files,   # NEW — scoped re-validation
        "agent_node": "validation_agent",
        "node_timings": timings,
    }


# ── Validation approval node ──────────────────────────────────────────────────

def validation_approval_node(state: GraphState):
    print("--- [Validation Approval Node] STARTED ---")
    command_details = state.get("validation_pending_command", "")
    approval_count = state.get("validation_approval_count", 0)

    user_decision = interrupt({
        "type": "command_approval",
        "instruction": (
            f"🔍 **Validator wants to run a command ({approval_count}/{MAX_APPROVAL_RETRIES}):**\n\n"
            f"{command_details}\n\n"
            f"Type **approve** to allow or **reject** to skip."
        ),
        "content_to_review": command_details,
    })

    print(f"--- [Validation Approval Node] User decision: {user_decision} ---")
    return {
        "validation_user_decision": user_decision,
        "agent_node": "validation_agent",
    }