from typing import Any
from dotenv import load_dotenv
import os
import time
from models.state import GraphState
from models.project_context import ProjectContext

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")


def _read_summary_from_disk(workspace_path: str) -> str:
    summary_path = os.path.join(workspace_path, "PROJECT_SUMMARY.md")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return f.read()
    return "PROJECT_SUMMARY.md not yet created by the coder agent."


def _extract_todos_from_result(result: Any) -> list:
    messages = []
    if isinstance(result, dict) and result.get("messages"):
        messages = result["messages"]
    elif hasattr(result, "messages"):
        messages = result.messages

    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "write_todos":
                raw_input = block.get("input", {})
                if isinstance(raw_input, list):
                    todos = raw_input
                elif isinstance(raw_input, dict):
                    for key in ("todos", "items", "tasks"):
                        if key in raw_input and isinstance(raw_input[key], list):
                            todos = raw_input[key]
                            break
                    else:
                        todos = []
                else:
                    todos = []

                normalized = []
                for item in todos:
                    if isinstance(item, dict):
                        norm = dict(item)
                        if norm.get("status") == "done":
                            norm["status"] = "completed"
                        normalized.append(norm)
                return normalized
    return []


async def coder_node(state: GraphState, coder_agent: Any):
    """Execute coding agent — single agent handles all implementation."""
    t_start = time.time()
    print("--- [Coder Node] STARTED ---")

    workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])

    # ── Load ProjectContext from disk ─────────────────────────────────────────
    ctx = ProjectContext.load(workspace_path)
    claude_md_exists = os.path.exists(os.path.join(workspace_path, "CLAUDE.md"))
    context_hint = ""
    if ctx:
        context_hint = f"""
SHARED PROJECT CONTEXT (from CLAUDE.md — read it first with read_file("/CLAUDE.md")):
  Backend:  {ctx.backend_framework}
  Frontend: {ctx.frontend_framework}
  Database: {ctx.database}
  Backend root:  {ctx.backend_root}
  Frontend root: {ctx.frontend_root}
  Pinned versions (use EXACTLY these in config files):
    {chr(10).join(f'    {k}: {v}' for k, v in ctx.pinned_versions.items())}

CRITICAL: read_file("/CLAUDE.md") MUST be your first action.
"""

    # ── Build message ─────────────────────────────────────────────────────────
    message = ""
    if state.get("code_summary"):
        # Re-invocation with feedback
        failed_files = state.get("validation_failed_files", [])
        files_hint = ""
        if failed_files:
            files_hint = f"""
SCOPE OF FIXES — only fix these files (do not touch other files):
{chr(10).join(f'  - {f}' for f in failed_files)}
"""
        message = f"""Previous Summary:
{state['code_summary']}

{context_hint}

VALIDATION FEEDBACK:
{state.get('validation_comments', '')}

{files_hint}

ACTION REQUIRED:
    1. read_file("/CLAUDE.md") — your first action, always.
    2. Read the validation comments carefully.
    3. Extract the "MISSING/INCOMPLETE FEATURES" section.
    4. Use write_todos() to create tasks for each missing/incomplete feature.
    5. Fix ONLY the files listed in "SCOPE OF FIXES" above.
    6. After completing EACH task, immediately call write_todos() with that
       task's status changed to "completed" before moving to the next task.
    7. Update PROJECT_SUMMARY.md when all fixes are complete.

IMPORTANT:
- Only create ONE markdown file: PROJECT_SUMMARY.md
- Do not create CONTRIBUTING.md, SETUP.md, or any other .md files
- Call write_todos() after completing each task.
"""
    else:
        # Initial invocation
        message = f"""Implement this complete project plan:

{state['planner_response']}

{context_hint}

CRITICAL — HARD CONSTRAINT ON write_file():
Your write_file() tool is LOCKED for the first 3 steps of this workflow.
The ONLY file you write directly is PROJECT_SUMMARY.md in the very last step.
Every other file is written by your subagents (backend-agent, frontend-agent, config-agent).
Calling write_file() before step 9 will corrupt the workspace.

WORKFLOW — follow this exactly:
    1. read_file("/CLAUDE.md") — ALWAYS your absolute first action.
    2. ls("/") to see current workspace state.
    3. Call write_todos() with ALL tasks. Set first task to "in_progress", rest "pending".
       Tasks: Backend implementation | Frontend implementation |
              Config and dependency files | Review and verification | Write PROJECT_SUMMARY.md
    4. task("backend-agent", ...) — delegate backend. Include CLAUDE.md context in your spec.
    5. Verify backend: read_file() on 3 key files. If stubs found → re-delegate immediately.
    6. task("frontend-agent", ...) — delegate frontend. Include CLAUDE.md context + API routes.
    7. Verify frontend: read_file() on App.tsx / layout.tsx / one page component.
    8. task("config-agent", ...) — delegate config. Pass pinned_versions from CLAUDE.md explicitly.
    9. FINAL REVIEW: read_file() on requirements.txt and package.json. Fix mismatches.
    10. write_file("/PROJECT_SUMMARY.md", ...) — THIS IS YOUR FIRST AND ONLY write_file() call.
    11. write_todos() — mark all tasks completed.

STEP 10 IS THE FIRST TIME YOU MAY CALL write_file(). Not before.

PROJECT_SUMMARY.md must include:
    - Project overview and features
    - Complete file structure
    - LOCAL SETUP & RUNNING INSTRUCTIONS with EXACT directories per command
    - Environment variables (with sample .env content and which directory)
    - How to run the app (exact command + exact directory + expected port/URL)

IMPORTANT:
    - Only create ONE markdown file: PROJECT_SUMMARY.md
    - No deployment code unless explicitly requested
    - Use the pinned versions from CLAUDE.md — do not infer versions yourself
"""

    result = await coder_agent.ainvoke(
        {"messages": [{"role": "user", "content": message}]}
    )

    # ── Read summary from disk ────────────────────────────────────────────────
    summary_text = _read_summary_from_disk(workspace_path)
    todos = _extract_todos_from_result(result)

    elapsed = time.time() - t_start
    print(f"--- [Coder Node] COMPLETED in {elapsed:.1f}s ---")

    # Increment retry count on re-invocations
    new_retry_count = state.get("coding_retry_count", 0) + (1 if state.get("code_summary") else 0)

    # Update node_timings
    timings = dict(state.get("node_timings", {}))
    timings["coder_agent"] = elapsed

    return {
        "code_summary": summary_text,
        "todos": todos,
        "agent_node": "coder",
        "current_node": "coder_agent",
        "status": "running",
        "validation_status": "",
        "validation_comments": "",
        "coding_retry_count": new_retry_count,
        "node_timings": timings,
    }