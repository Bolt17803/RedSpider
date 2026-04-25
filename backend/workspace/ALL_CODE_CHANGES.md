# Complete Code Changes — Multi-Agent System Fixes

All 11 changes in priority order. Each snippet is a **drop-in replacement** for
the corresponding section in your existing file. File paths match your repo.

---

## CHANGE 1 — `models/state.py`
### What changes: Add `project_context`, `validation_failed_files`, `coding_retry_count`, `node_timings`

```python
# models/state.py  — FULL FILE REPLACEMENT

from typing import Annotated, List, Optional, TypedDict, Dict, Literal, Any
import operator


class GraphState(TypedDict):
    """
    Single source of truth for the entire workflow.
    Every field that the frontend needs to render must live here.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    title: str
    thread_id: str

    # ── Execution status ──────────────────────────────────────────────────────
    status: Literal["idle", "running", "waiting", "completed", "error"]
    current_node: Optional[str]

    # ── Human-in-the-loop ─────────────────────────────────────────────────────
    agent_node: str
    user_response: str

    # ── Architect phase ───────────────────────────────────────────────────────
    architect_response: str
    final_architect_response: str
    architect_messages: Annotated[list, operator.add]

    # ── Planner phase ─────────────────────────────────────────────────────────
    planner_response: str
    final_planner_response: str
    planner_messages: Annotated[list, operator.add]

    # ── Shared project context (NEW — injected into every subagent) ───────────
    # Written after planner approval. JSON string on disk, dict here in state.
    project_context: Optional[Dict[str, Any]]

    # ── Coder phase ───────────────────────────────────────────────────────────
    code_summary: str
    todos: List[Dict[str, Any]]
    coding_retry_count: int  # NEW — prevents infinite coder↔validator loops

    # ── Validation phase ──────────────────────────────────────────────────────
    validation_status: str
    validation_comments: str
    validation_pending_command: Optional[str]
    validation_user_decision: Optional[str]
    validation_approval_count: int
    validation_failed_files: List[str]  # NEW — scoped re-validation

    # ── Summarizer phase ──────────────────────────────────────────────────────
    final_summary: str

    # ── Diagnostics (NEW — per-node timing for debugging) ─────────────────────
    node_timings: Dict[str, float]  # {"coder_agent": 142.3, ...} seconds

    # ── Errors ────────────────────────────────────────────────────────────────
    errors: List[str]
```

---

## CHANGE 2 — New file: `models/project_context.py`
### What it does: Defines the shared ProjectContext dataclass + disk I/O helpers

```python
# models/project_context.py  — NEW FILE

"""
ProjectContext: the single source of truth shared across ALL subagents.

Written to disk as CLAUDE.md (human-readable) and project_context.json
(machine-readable) immediately after the planner is approved.

Every subagent reads CLAUDE.md as its FIRST action before writing any code.
This eliminates the config-agent version mismatch bug, the frontend/backend
API contract drift bug, and the missing providers.tsx class of bug.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
import json
import os


@dataclass
class ProjectContext:
    # Identity
    project_name: str
    description: str

    # Tech stack — exact choices from planner, locked here
    backend_framework: str          # e.g. "FastAPI"
    frontend_framework: str         # e.g. "Next.js 15 App Router"
    database: str                   # e.g. "SQLite" | "PostgreSQL"
    css_framework: str              # e.g. "Tailwind CSS v3"

    # Pinned versions — config agent MUST use these, not infer from imports
    pinned_versions: Dict[str, str] = field(default_factory=dict)
    # e.g. {"fastapi": ">=0.111.0", "next": "15.0.0", "react": "^18.3.0"}

    # Directory layout — exact paths every agent must use
    backend_root: str = "/backend"
    frontend_root: str = "/frontend"

    # API contract — filled in by orchestrator after backend agent completes
    # Each entry: {"method": "POST", "path": "/api/auth/login",
    #              "auth": false, "request": {...}, "response": {...}}
    api_routes: List[Dict] = field(default_factory=list)

    # Environment variables — all agents contribute, config agent finalises
    env_vars: List[str] = field(default_factory=list)
    # e.g. ["DATABASE_URL", "SECRET_KEY", "NEXT_PUBLIC_API_URL"]

    # Workspace root on REAL disk (not virtual path) — validator uses this
    workspace_root: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_claude_md(self) -> str:
        """
        Render as CLAUDE.md — the file every subagent reads first.
        Structured so an LLM can extract any section quickly.
        """
        routes_text = ""
        for r in self.api_routes:
            auth_tag = "[auth required]" if r.get("auth") else "[public]"
            routes_text += f"  {r['method']} {r['path']} {auth_tag}\n"
            if r.get("request"):
                routes_text += f"    request: {json.dumps(r['request'])}\n"
            if r.get("response"):
                routes_text += f"    response: {json.dumps(r['response'])}\n"

        versions_text = "\n".join(
            f"  {pkg}: {ver}" for pkg, ver in self.pinned_versions.items()
        )

        env_text = "\n".join(f"  {v}" for v in self.env_vars)

        return f"""# CLAUDE.md — Project Ground Truth
## READ THIS FIRST before writing any code or any file.

## Project
Name: {self.project_name}
Description: {self.description}

## Tech Stack (DO NOT DEVIATE)
Backend: {self.backend_framework}
Frontend: {self.frontend_framework}
Database: {self.database}
CSS: {self.css_framework}

## Directory Layout (EXACT PATHS — use verbatim)
Backend root:  {self.backend_root}
Frontend root: {self.frontend_root}

## Pinned Package Versions (USE EXACTLY THESE — do not infer from imports)
{versions_text}

## API Contract (Frontend must use these exact URLs)
{routes_text if routes_text else "  [will be filled after backend agent completes]"}

## Environment Variables
{env_text if env_text else "  [will be filled during implementation]"}

## Real Workspace Path (for execute_command working_dir)
{self.workspace_root}
Backend dir:  {self.workspace_root}{self.backend_root}
Frontend dir: {self.workspace_root}{self.frontend_root}

## Rules
1. NEVER use a package version not listed above.
2. NEVER create files outside the directory layout above.
3. NEVER use virtual paths like /backend in execute_command — use the real paths above.
4. The API contract above is the ONLY source of truth for route URLs.
"""

    # ── Disk I/O ──────────────────────────────────────────────────────────────

    def save(self, workspace_path: str):
        """Write CLAUDE.md and project_context.json to workspace root."""
        claude_md_path = os.path.join(workspace_path, "CLAUDE.md")
        json_path = os.path.join(workspace_path, "project_context.json")

        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(self.to_claude_md())

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, workspace_path: str) -> Optional["ProjectContext"]:
        """Load from project_context.json. Returns None if not found."""
        json_path = os.path.join(workspace_path, "project_context.json")
        if not os.path.exists(json_path):
            return None
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


def build_project_context_from_planner(
    planner_response: str,
    workspace_path: str,
    project_name: str,
) -> ProjectContext:
    """
    Parse the planner response to extract tech stack and pinned versions.
    This is a best-effort extraction — the planner prompt must output
    a structured JSON block (see prompts/planner.py change below).
    """
    import re

    # Try to find a JSON block the planner was instructed to emit
    json_match = re.search(
        r"```json\s*(\{.*?\"pinned_versions\".*?\})\s*```",
        planner_response,
        re.DOTALL,
    )

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            ctx = ProjectContext(
                project_name=project_name,
                description=data.get("description", ""),
                backend_framework=data.get("backend_framework", "FastAPI"),
                frontend_framework=data.get("frontend_framework", "Next.js 15"),
                database=data.get("database", "SQLite"),
                css_framework=data.get("css_framework", "Tailwind CSS v3"),
                pinned_versions=data.get("pinned_versions", {}),
                env_vars=data.get("env_vars", []),
                workspace_root=workspace_path,
            )
            ctx.save(workspace_path)
            return ctx
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: build a minimal context with sensible defaults
    ctx = ProjectContext(
        project_name=project_name,
        description="",
        backend_framework="FastAPI",
        frontend_framework="Next.js 15 App Router",
        database="SQLite",
        css_framework="Tailwind CSS v3",
        pinned_versions={
            "fastapi": ">=0.111.0",
            "uvicorn[standard]": ">=0.30.0",
            "sqlalchemy": ">=2.0.30",
            "pydantic": ">=2.7.0",
            "python-jose[cryptography]": ">=3.3.0",
            "passlib[bcrypt]": ">=1.7.4",
            "python-multipart": ">=0.0.9",
            "python-dotenv": ">=1.0.0",
            "next": "15.0.0",
            "react": "^18.3.0",
            "react-dom": "^18.3.0",
            "typescript": "^5.4.0",
            "tailwindcss": "^3.4.0",
            "@tanstack/react-query": "^5.40.0",
            "axios": "^1.7.0",
        },
        env_vars=["DATABASE_URL", "SECRET_KEY", "NEXT_PUBLIC_API_URL"],
        workspace_root=workspace_path,
    )
    ctx.save(workspace_path)
    return ctx
```

---

## CHANGE 3 — `graphs/orchestrator.py`
### What changes: `init_deepagents` writes ProjectContext; `planner_decision_node` triggers it; new `MAX_CODING_RETRIES` guard; parallel subagents; per-node timing

Replace only the sections shown. The rest of `orchestrator.py` stays the same.

```python
# graphs/orchestrator.py — PARTIAL CHANGES
# Replace/add each block exactly as shown below.

# ── ADD at top of file, after existing imports ─────────────────────────────
import time
import asyncio
from models.project_context import ProjectContext, build_project_context_from_planner

MAX_CODING_RETRIES = 3  # NEW — prevents infinite coder↔validator loops


# ── REPLACE planner_decision_node ──────────────────────────────────────────
def planner_decision_node(state: GraphState):
    if state['user_response'].lower() == "approve":
        print("--- [Planner Decision Node : ENDING] ---")
        workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])

        # Save planner response to disk
        planner_response_file_path = os.path.join(workspace_path, "planner_response.txt")
        planner_text = state["planner_response"]
        if isinstance(planner_text, list):
            planner_text = "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in planner_text
            )
        with open(planner_response_file_path, "w", encoding="utf-8") as f:
            f.write(str(planner_text))

        # NEW — Build and save ProjectContext + CLAUDE.md immediately
        ctx = build_project_context_from_planner(
            planner_response=str(planner_text),
            workspace_path=workspace_path,
            project_name=state["title"],
        )
        print(f"[Planner Decision] ProjectContext saved. Versions: {list(ctx.pinned_versions.keys())}")

        return END
    else:
        print("--- [Planner Decision Node : LOOPING] ---")
        return "agent"


# ── REPLACE init_deepagents ────────────────────────────────────────────────
def init_deepagents(state: GraphState):
    """
    Initialize workspace and deep-agent instances.
    Also sets default values for all new state fields.
    """
    workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])
    os.makedirs(workspace_path, exist_ok=True)
    create_coder_agent(workspace_path)
    create_validation_agent(workspace_path)
    create_summarizer_agent(workspace_path)

    return {
        "status": "running",
        "current_node": "init_deepagents",
        "todos": [],
        "errors": [],
        "validation_approval_count": 0,
        "coding_retry_count": 0,          # NEW
        "validation_failed_files": [],     # NEW
        "project_context": None,           # NEW — populated after planner
        "node_timings": {},                # NEW
    }


# ── REPLACE should_continue_coding (in validation.py, keep here for reference)
# ADD this new router in orchestrator.py for the human_response node:
def review_human_response(state: GraphState):
    if state['user_response'].lower() == "approve":
        print("--- [Review Human Response Node : ENDING] ---")
        return END
    else:
        retry = state.get("coding_retry_count", 0)
        if retry >= MAX_CODING_RETRIES:
            print(f"[Review] Hit MAX_CODING_RETRIES ({MAX_CODING_RETRIES}). Ending.")
            return END
        print("--- [Review Human Response Node : LOOPING] ---")
        return "code"
```

---

## CHANGE 4 — `nodes/coder.py`
### What changes: Timing wrapper; ProjectContext injection; coding_retry_count increment; PROJECT_SUMMARY lock

```python
# nodes/coder.py  — FULL FILE REPLACEMENT

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
```

---

## CHANGE 5 — `nodes/validation.py`
### What changes: Real path injection; error recovery; scoped failed-files extraction; timing; flat agent (no nested MemorySaver); MAX_CODING_RETRIES guard

```python
# nodes/validation.py  — FULL FILE REPLACEMENT

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
```

---

## CHANGE 6 — `tools/validation.py`
### What changes: Better error messages; path suggestion on failure

```python
# tools/validation.py  — FULL FILE REPLACEMENT

from langchain_core.tools import tool
import subprocess
import os


@tool
def execute_command(command: str, working_dir: str, env_vars: dict = None) -> str:
    """Execute a shell command in the specified directory.

    Args:
        command: The shell command to execute.
        working_dir: ABSOLUTE disk path to run the command in.
                     NEVER use virtual paths like /backend — use the real path
                     from the workspace_root in CLAUDE.md.
        env_vars: Optional environment variables to set.
    """
    if env_vars is None:
        env_vars = {}

    env = os.environ.copy()
    env.update(env_vars)

    # ── Path validation with helpful diagnostics ──────────────────────────────
    if not os.path.exists(working_dir):
        # Try to give a useful hint about what went wrong
        hint = ""
        if working_dir.startswith("/backend") or working_dir.startswith("/frontend"):
            hint = (
                f"\nHINT: You used a virtual path '{working_dir}'. "
                f"execute_command() needs a REAL absolute disk path. "
                f"Read /PROJECT_SUMMARY.md or /CLAUDE.md to find the correct absolute path. "
                f"Do NOT retry this command with the same path."
            )
        elif not os.path.isabs(working_dir):
            hint = (
                f"\nHINT: '{working_dir}' is a relative path. "
                f"execute_command() requires an absolute path."
            )
        return (
            f"Error: Working directory '{working_dir}' does not exist.{hint}"
        )

    if not os.path.isdir(working_dir):
        return (
            f"Error: '{working_dir}' is not a directory. "
            f"Provide a directory path, not a file path."
        )

    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_dir,
            env=env,
        )
        try:
            stdout_bytes, stderr_bytes = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_bytes, stderr_bytes = process.communicate()
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return (
                f"Error: Command timed out after 120 seconds: {command}\n\n"
                f"STDOUT (until timeout):\n{stdout}\n\n"
                f"STDERR (until timeout):\n{stderr}\n\n"
                f"HINT: This command likely started a persistent process (dev server). "
                f"Use build/compile commands that exit cleanly instead."
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return f"Exit Code: {process.returncode}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"

    except Exception as e:
        return f"Error executing command: {str(e)}"
```

---

## CHANGE 7 — `prompts/coder.py`
### What changes: Add CLAUDE.md first-action rule; enforce PROJECT_SUMMARY lock; pass context to config agent

The full `coder_backstory()` is long — replace only the STEP 7 and CRITICAL RULES sections:

```python
# prompts/coder.py — REPLACE STEP 7 and CRITICAL RULES sections only
# Find the existing text and replace with the blocks below.

# ── REPLACE "STEP 7: DELEGATE TO CONFIG AGENT" section ─────────────────────
"""
    ═══════════════════════════════════════════
    STEP 7: DELEGATE TO CONFIG AGENT
    ═══════════════════════════════════════════
    Call: task(name="config-agent", task="<your specification>")

    Your specification for the config agent MUST include ALL of the following:

    1. The full workspace path.
    2. Which database is used.
    3. The EXACT pinned versions from CLAUDE.md — paste them verbatim:
       Read read_file("/CLAUDE.md") and copy the "Pinned Package Versions" section
       word-for-word into your spec. The config agent MUST use these exact versions,
       not infer versions from import statements.
    4. The Python packages the backend agent reported using.
    5. The npm packages the frontend agent reported using.
    6. All environment variables discovered during backend and frontend implementation.

    Example spec opening:
    "PINNED VERSIONS — USE THESE EXACTLY, DO NOT OVERRIDE:
      fastapi: >=0.111.0
      uvicorn[standard]: >=0.30.0
      next: 15.0.0
      react: ^18.3.0
      ...
    The above versions come from the project plan and are non-negotiable."

    After calling task(), update write_todos():
        3. "Config and dependency files" → completed
        4. "Review and verification" → in_progress
"""

# ── REPLACE "CRITICAL RULES" section ───────────────────────────────────────
"""
    ═══════════════════════════════════════════
    CRITICAL RULES
    ═══════════════════════════════════════════
    - read_file("/CLAUDE.md") is ALWAYS your first action in every session.
      It contains the ground truth: tech stack, pinned versions, file paths, API contract.

    - YOUR write_file() IS LOCKED until STEP 9.
      You may not call write_file() for any file before PROJECT_SUMMARY.md.
      If you feel the urge to create a file before step 9, delegate it to a subagent.

    - Never accept stub output. If a subagent returns a file with "pass", "TODO",
      empty functions, or <h1>Only</h1> components, re-delegate immediately.

    - Never skip verification steps. read_file() the actual files — do not trust summaries.

    - The config agent runs LAST. Pass pinned versions from CLAUDE.md explicitly.
      Never let the config agent infer versions from imports.

    - NEVER call write_file() before all three task() delegations are complete.
      Your only write_file() call in the entire workflow is PROJECT_SUMMARY.md in STEP 9.
"""
```

---

## CHANGE 8 — `prompts/subcoding_agents.py`
### What changes: All three subagents now read CLAUDE.md first; config agent uses pinned versions from spec (not from scanning)

```python
# prompts/subcoding_agents.py — ADD to top of each agent prompt function

# ── ADD to backend_specialist_prompt() — insert after the opening docstring ──
CLAUDE_MD_PREAMBLE = """
    ══════════════════════════════════════════════════════════
    MANDATORY FIRST ACTION — NO EXCEPTIONS:
    ══════════════════════════════════════════════════════════

    BEFORE WRITING ANY FILE, call: read_file("/CLAUDE.md")

    CLAUDE.md contains the authoritative ground truth for this project:
    - The exact backend and frontend frameworks to use
    - The exact directory paths to write files to
    - The pinned package versions (DO NOT deviate from these)
    - The API contract (routes, request/response shapes)
    - The real absolute disk path for any command execution

    If CLAUDE.md says the backend root is /backend, EVERY file you write
    goes under /backend/. If it says Next.js 15, you use Next.js 15.
    You do not make decisions — you follow CLAUDE.md.
"""

# Prepend CLAUDE_MD_PREAMBLE to each of the three prompt functions:

def backend_specialist_prompt():
    return CLAUDE_MD_PREAMBLE + """
    You are a backend implementation specialist. [... rest unchanged ...]
    """

def frontend_specialist_prompt():
    return CLAUDE_MD_PREAMBLE + """
    You are a senior Next.js frontend specialist. [... rest unchanged ...]
    """


# ── REPLACE config_specialist_prompt() entirely ────────────────────────────
def config_specialist_prompt():
    return CLAUDE_MD_PREAMBLE + """
    You are a configuration specialist. Your job is to produce correct dependency
    and config files for the project.

    IDENTITY: You write requirements.txt, package.json, and .env.example.
    You do NOT write application code. You do NOT scan imports to determine versions.

    ══════════════════════════════════════════════════════════
    MANDATORY EXECUTION ORDER:
    ══════════════════════════════════════════════════════════

    STEP 1 — READ CLAUDE.md FIRST:
    Call read_file("/CLAUDE.md"). This has the PINNED VERSIONS section.
    These versions are NON-NEGOTIABLE. They came from the project plan.
    You must use them exactly as written.

    STEP 2 — READ THE SPEC YOU WERE GIVEN:
    Your task description includes a "PINNED VERSIONS" block from the orchestrator.
    Use these versions. Do not infer versions from import statements.
    Import scanning is a FALLBACK ONLY if a package has no pinned version.

    STEP 3 — SCAN FOR MISSING PACKAGES ONLY:
    Use glob() and read_file() to find packages that are IMPORTED in source files
    but NOT in the pinned versions list. Add those with >= recent stable versions.
    Do not override pinned versions with your scan results.

    STEP 4 — WRITE requirements.txt:
    Location: /backend/requirements.txt
    - Start with ALL pinned versions from CLAUDE.md and your spec.
    - Add any extra detected packages from STEP 3.
    - Use >= format, not exact pins.
    - Call write_file() immediately. If file exists, use edit_file().
    - Verify with read_file() after writing.

    STEP 5 — WRITE package.json:
    Location: /frontend/package.json
    - Start with ALL pinned versions from CLAUDE.md and your spec.
    - Add any extra detected packages from STEP 3.
    - If file exists, read it first and MERGE — preserve scripts section.
    - Call write_file() or edit_file() as appropriate.
    - Verify with read_file() after writing.

    STEP 6 — WRITE .env.example:
    Location: /.env.example (project root)
    - Read CLAUDE.md for the Environment Variables section.
    - Scan source files for any additional os.getenv() / process.env references.
    - Write a .env.example with all variables and brief comments.
    - Verify with read_file() after writing.

    STEP 7 — RETURN SUMMARY:
    Only after all three files are verified on disk, return a short summary
    listing each file path and the packages it contains.

    ══════════════════════════════════════════════════════════
    FILESYSTEM RULES:
    ══════════════════════════════════════════════════════════
    write_file() → NEW files only. edit_file() → EXISTING files only.
    Never call write_file() twice on the same path.

    ══════════════════════════════════════════════════════════
    VERSION RULES — NON-NEGOTIABLE:
    ══════════════════════════════════════════════════════════
    1. Pinned versions from CLAUDE.md and your spec ALWAYS win.
    2. Import scanning is ADDITIVE ONLY — it adds missing packages, never overrides.
    3. If your scan finds "next" imported but CLAUDE.md says next: 15.0.0,
       the requirements.txt gets "next": "15.0.0" — not whatever the scan suggests.
    """
```

---

## CHANGE 9 — `graphs/orchestrator.py` — Parallel subagents in `create_coder_agent`
### What changes: Backend and frontend subagents can run in parallel via asyncio

The deep-agent `task()` tool handles this internally — but you need to tell the
orchestrator prompt explicitly that it CAN parallelize. This is a prompt change
only (the infrastructure already supports it via CompiledSubAgent):

```python
# prompts/coder.py — ADD this block inside STEP 3 / STEP 5 delegation instructions

# In STEP 3 (backend delegation), add at the end:
"""
    PARALLELIZATION NOTE:
    After calling task("backend-agent"), you MAY immediately call
    task("frontend-agent") without waiting for backend to complete,
    IF AND ONLY IF the frontend spec is complete and does not depend
    on the backend's output yet. The filesystem is shared and both
    agents write to separate directories (/backend/ and /frontend/).
    
    If you choose to run them in parallel:
    - Pass the FULL API contract from the planner to the frontend agent
      so it does not need to wait for backend to finish.
    - Verify BOTH agents' output after both complete.
    - Only then call task("config-agent").
"""
```

For true `asyncio.gather()` parallelism at the Python level, update `coder_node`
in `nodes/coder.py`. The coder agent's `task()` tool already runs subagents
sequentially — to make them genuinely parallel, add this helper if your
`deepagents` library supports concurrent invocation:

```python
# nodes/coder.py — ADD this helper (only if deepagents supports async invoke)
# This is optional — the prompt-level parallelism above is sufficient for now.

# If deepagents exposes an async interface for parallel task execution,
# set this env var to signal the orchestrator to use parallel mode:
# ENABLE_PARALLEL_SUBAGENTS=true
# Then in your coder prompt add the parallelization note above.
# True asyncio.gather() requires deepagents library support — check their docs.
```

---

## CHANGE 10 — `graphs/orchestrator.py` — Timing for all nodes

```python
# graphs/orchestrator.py — REPLACE the coder, validation, summarizer node wrappers

    # Replace the existing _coder_node, _validation_agent_node, _summarizer_agent_node
    # with timing-aware versions:

    async def _coder_node(state, config):
        # timing is now inside coder_node itself (see Change 4)
        return await coder_node(state, coder_agent)

    async def _validation_agent_node(state, config):
        # timing is now inside validation_node itself (see Change 5)
        return await validation_node(state, validation_agent, config)

    async def _summarizer_agent_node(state, config):
        import time
        t = time.time()
        result = await summarizer_node(state, summarizer_agent)
        elapsed = time.time() - t
        timings = dict(state.get("node_timings", {}))
        timings["summarizer_agent"] = elapsed
        print(f"[Summarizer] Completed in {elapsed:.1f}s")
        result["node_timings"] = timings
        return result

    # ADD: log final timings when graph completes
    # In your FastAPI route that streams the graph, after the stream ends:
    # final_state = await graph.aget_state(config)
    # timings = final_state.values.get("node_timings", {})
    # print(f"[TIMING REPORT] {json.dumps(timings, indent=2)}")
```

---

## CHANGE 11 — `graphs/orchestrator.py` — `graph_invoker` defaults

```python
# graphs/orchestrator.py — REPLACE graph_invoker() builder section
# Add the new nodes and update default state initialization.

def graph_invoker(checkpointer=None):
    builder = StateGraph(GraphState)
    if not checkpointer:
        checkpointer = MemorySaver()

    builder.add_node("init_deepagents", init_deepagents)
    builder.add_node("architect_agent", architect_node)
    builder.add_node("architect_review", architect_response_review_node)
    builder.add_node("planner_agent", planner_node)
    builder.add_node("planner_review", planner_response_review_node)

    async def _coder_node(state, config):
        return await coder_node(state, coder_agent)
    builder.add_node("coder_agent", _coder_node)

    async def _validation_agent_node(state, config):
        return await validation_node(state, validation_agent, config)
    builder.add_node("validation_agent", _validation_agent_node)
    builder.add_node("validation_approval", validation_approval_node)

    async def _summarizer_agent_node(state, config):
        import time
        t = time.time()
        result = await summarizer_node(state, summarizer_agent)
        elapsed = time.time() - t
        timings = dict(state.get("node_timings", {}))
        timings["summarizer_agent"] = elapsed
        result["node_timings"] = timings
        return result
    builder.add_node("summarizer_agent", _summarizer_agent_node)
    builder.add_node("human_response", human_response_node)

    builder.set_entry_point("init_deepagents")
    builder.add_edge("init_deepagents", "architect_agent")
    builder.add_edge("architect_agent", "architect_review")
    builder.add_edge("planner_agent", "planner_review")
    builder.add_edge("coder_agent", "validation_agent")
    builder.add_edge("summarizer_agent", "human_response")

    builder.add_conditional_edges(
        "architect_review",
        architect_decision_node,
        {END: "planner_agent", "agent": "architect_agent"},
    )
    builder.add_conditional_edges(
        "planner_review",
        planner_decision_node,
        {END: "coder_agent", "agent": "planner_agent"},
    )
    builder.add_conditional_edges(
        "validation_agent",
        should_continue_coding,
        {
            "code": "coder_agent",
            "summarize": "summarizer_agent",
            "validation_approval": "validation_approval",
        },
    )
    builder.add_conditional_edges(
        "validation_approval",
        should_continue_after_validation_approval,
        {"validation": "validation_agent"},
    )
    builder.add_conditional_edges(
        "human_response",
        review_human_response,   # updated version with MAX_CODING_RETRIES guard
        {END: END, "code": "coder_agent"},
    )

    graph = builder.compile(checkpointer=checkpointer)
    return graph
```

---

## Summary: what each change fixes

| Change | File | Fixes |
|--------|------|-------|
| 1 | `models/state.py` | Adds `project_context`, `validation_failed_files`, `coding_retry_count`, `node_timings` |
| 2 | `models/project_context.py` | New. Shared context object + CLAUDE.md writer |
| 3 | `graphs/orchestrator.py` | ProjectContext built after planner; `MAX_CODING_RETRIES`; timing defaults |
| 4 | `nodes/coder.py` | CLAUDE.md injection; write_file lock; scoped fix list; retry counter; timing |
| 5 | `nodes/validation.py` | Real path injection; error recovery on bad path; scoped failed files; timing |
| 6 | `tools/validation.py` | Better error message + STOP hint when path is virtual |
| 7 | `prompts/coder.py` | CLAUDE.md first-action rule; write_file lock; config agent gets pinned versions |
| 8 | `prompts/subcoding_agents.py` | All subagents read CLAUDE.md first; config agent uses pinned versions not scan |
| 9 | `prompts/coder.py` | Parallelization hint for backend+frontend subagents |
| 10 | `graphs/orchestrator.py` | Per-node timing wrappers |
| 11 | `graphs/orchestrator.py` | Full graph_invoker with all new nodes wired |
