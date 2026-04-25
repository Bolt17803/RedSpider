"""
Multi-Agent Coding Team — deepagents SDK
==========================================
Built strictly from:
  - https://docs.langchain.com/oss/python/deepagents/subagents
  - https://docs.langchain.com/oss/python/deepagents/backends
  - https://docs.langchain.com/oss/python/deepagents/overview

KEY FIXES this file addresses:
  1. Subagent not being called → explicit system prompt + clear descriptions
  2. File conflicts → FilesystemBackend with virtual_mode=True + scoped subdirs per agent
  3. Context bloat → subagents return concise summaries, raw data written to files
  4. Wrong/incomplete output → detailed system prompts with output format requirements
  5. StateBackend shared state confusion → switched to FilesystemBackend for real file I/O
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
load_dotenv("../.env")

PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")

# Deepagents built-in filesystem tools (ls, read_file, edit_file, grep, …) only
# accept virtual paths like "/foo.txt" anchored at the backend root. Prompts
# must not encourage passing Windows paths from project_dir into those tools.
VIRTUAL_FS_RULES = """
## Virtual filesystem (built-in ls / read_file / write_file / edit_file / grep)
These tools use paths under `/` only (forward slashes, leading `/`). The project root is `/`.
Examples: `ls("/")`, `read_file("/README.md")`, `write_file("/src/app.py", ...)`.
Never pass Windows absolute paths (e.g. `C:\\Users\\...`) to these tools — they will error.
"""


# ---------------------------------------------------------------------------
# Path safety (Windows: Path(root) / "/x" or / "C:\\x" → escapes project_dir)
# ---------------------------------------------------------------------------

def _resolve_path_under_project(project_dir: str, path: str) -> Path:
    """
    Join user path to project root without allowing absolute / drive paths.
    Raises ValueError with a message suitable for the model to self-correct.
    """
    root = Path(project_dir).resolve()
    cleaned = (path or "").replace("\\", "/").strip().lstrip("/")
    if not cleaned:
        raise ValueError("Path is empty; use a relative path like src/main.py")
    first = cleaned.split("/", 1)[0]
    if len(first) == 2 and first[1] == ":":
        raise ValueError(
            f"Absolute Windows paths are not allowed (got {path!r}). "
            "Use a path relative to the project root, e.g. requirements.txt"
        )
    candidate = (root / cleaned).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError(
            f"Path escapes project directory: {path!r}. "
            "Use only relative paths under the project root."
        ) from e
    return candidate


def _format_tool_input(inp: Any, max_len: int = 2000) -> str:
    try:
        s = json.dumps(inp, default=str, ensure_ascii=False)
    except TypeError:
        s = str(inp)
    if len(s) > max_len:
        return s[: max_len - 20] + "… (truncated)"
    return s


def _print_stream_chunk(chunk: Any) -> None:
    """Print model tokens; include reasoning / thinking blocks when present."""
    # AIMessageChunk: .content may be str or list of blocks (e.g. Anthropic)
    content = getattr(chunk, "content", None)
    if content is None:
        return
    if isinstance(content, str) and content:
        print(content, end="", flush=True)
        return
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type", "")
                if btype in ("thinking", "reasoning"):
                    text = block.get("thinking") or block.get("text") or block.get("reasoning")
                    if text:
                        print(f"\n[thinking]\n{text}\n[/thinking]\n", flush=True)
                elif "text" in block:
                    print(block["text"], end="", flush=True)
            elif isinstance(block, str):
                print(block, end="", flush=True)
    # Provider-specific extended fields
    for key in ("reasoning_content", "thinking"):
        extra = getattr(chunk, key, None)
        if extra:
            print(f"\n[{key}]\n{extra}\n[/{key}]\n", flush=True)
    ak = getattr(chunk, "additional_kwargs", None) or {}
    for key in ("reasoning_content", "thinking", "reasoning"):
        if ak.get(key):
            print(f"\n[{key}]\n{ak[key]}\n[/{key}]\n", flush=True)


def _print_harness_event(event: dict[str, Any]) -> None:
    """Stream high-signal LangGraph v2 events to the terminal."""
    ev = event.get("event", "")
    name = event.get("name", "")
    tags = event.get("tags") or []

    depth = ""
    if tags:
        depth = f" [{' > '.join(str(t) for t in tags[-3:])}]"

    if ev == "on_tool_start":
        data = event.get("data") or {}
        inp = data.get("input")
        print(f"\n── tool_start : {name}{depth} ──\n{_format_tool_input(inp)}\n", flush=True)
    elif ev == "on_tool_end":
        data = event.get("data") or {}
        out = data.get("output")
        preview = _format_tool_input(out, max_len=1500)
        print(f"\n── tool_end : {name}{depth} ──\n{preview}\n", flush=True)
    elif ev == "on_chat_model_stream":
        data = event.get("data") or {}
        chunk = data.get("chunk")
        if chunk is not None:
            _print_stream_chunk(chunk)
# ---------------------------------------------------------------------------
# File tools scoped to the project directory
# These are given to subagents so they can read/write code files.
# ---------------------------------------------------------------------------

def make_file_tools(project_dir: str):
    """
    Returns a set of plain Python file tools scoped to project_dir.
    These are intentionally simple — the backend handles path enforcement.
    """
    from langchain_core.tools import tool

    @tool
    def read_file(path: str) -> str:
        """Read a file. Path should be relative to the project directory."""
        try:
            abs_path = _resolve_path_under_project(project_dir, path)
        except ValueError as e:
            return f"[ERROR] {e}"
        if not abs_path.exists():
            return f"[ERROR] File not found: {path}"
        return abs_path.read_text(encoding="utf-8")

    @tool
    def write_file(path: str, content: str) -> str:
        """
        Write content to a file. Path should be relative to project directory.
        Creates parent directories if needed.
        """
        try:
            abs_path = _resolve_path_under_project(project_dir, path)
        except ValueError as e:
            return f"[ERROR] {e}"
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
        return f"[OK] Written {len(content)} chars → {path}"

    @tool
    def edit_file(path: str, old_string: str, new_string: str) -> str:
        """
        Edit a file by replacing old_string with new_string.
        old_string must appear exactly once in the file.
        """
        try:
            abs_path = _resolve_path_under_project(project_dir, path)
        except ValueError as e:
            return f"[ERROR] {e}"
        if not abs_path.exists():
            return f"[ERROR] File not found: {path}"
        content = abs_path.read_text(encoding="utf-8")
        count = content.count(old_string)
        if count == 0:
            return f"[ERROR] String not found in {path}"
        if count > 1:
            return f"[ERROR] String appears {count} times — be more specific"
        abs_path.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
        return f"[OK] Edited {path}"

    @tool
    def list_files(path: str = ".") -> str:
        """List files in a directory relative to the project directory."""
        try:
            abs_path = _resolve_path_under_project(project_dir, path)
        except ValueError as e:
            return f"[ERROR] {e}"
        if not abs_path.exists():
            return f"[ERROR] Directory not found: {path}"
        entries = sorted(abs_path.rglob("*"))
        lines = []
        for e in entries:
            rel = e.relative_to(Path(project_dir))
            tag = "DIR" if e.is_dir() else "FILE"
            lines.append(f"  [{tag}] {rel}")
        return "\n".join(lines) if lines else "(empty)"

    return [read_file, write_file, edit_file, list_files]


# ---------------------------------------------------------------------------
# Subagent system prompts
# CRITICAL: subagents do NOT inherit the main agent's system prompt.
# Each one needs complete, self-contained instructions.
# ---------------------------------------------------------------------------

def make_architect_prompt(project_dir: str) -> str:
    return f"""You are a software architect subagent in a multi-agent coding team.

Your ONLY job is to:
1. Analyze the coding plan given to you
2. Decompose it into a list of atomic, non-overlapping implementation tasks
3. Decide which tasks can run in parallel vs which must be sequential
4. Write the architecture plan to a file

Project root on disk (for your awareness only; not for built-in file tools): {project_dir}
{VIRTUAL_FS_RULES}
For the custom tools read_file / write_file / edit_file / list_files, paths are relative to the project root (e.g. `architecture/plan.md`).
Never use a leading `/` or `C:\\...` — on Windows that resolves outside the project and will fail.

OUTPUT FORMAT — always write your plan to: architecture/plan.md
Structure it as:

```markdown
# Architecture Plan

## Overview
<brief description of what we're building>

## File Structure
<list of all files that will be created>

## Tasks
### Task 1: <name>
- Agent: <which specialized agent should do this>
- Files: <specific files to create/modify>
- Depends on: <task IDs this must wait for, or "none">
- Description: <what to implement>

### Task 2: ...
```

RULES:
- Never assign the same file to two tasks
- Keep tasks small and focused (1-3 files each)
- Return a concise summary (under 200 words) describing the plan
- Do NOT implement any code yourself
"""


def make_coder_prompt(project_dir: str, agent_name: str) -> str:
    return f"""You are a coding subagent ({agent_name}) in a multi-agent coding team.

Your ONLY job is to implement the specific task you are given.

Project root on disk (for your awareness only; not for built-in file tools): {project_dir}
{VIRTUAL_FS_RULES}
For the custom tools read_file / write_file / edit_file / list_files, paths are relative to the project root (e.g. `src/main.py`).
Never use a leading `/` or `C:\\...` — on Windows that resolves outside the project and will fail.

WORKFLOW:
1. Read architecture/plan.md to understand the full picture
2. Read any existing files relevant to your task
3. Implement the code completely — no TODOs, no placeholders
4. Write all files using write_file or edit_file
5. Return a completion report (see format below)

CODING STANDARDS:
- Write complete, working, production-quality code
- Add proper type hints and docstrings
- Handle edge cases and errors
- Follow existing code style in the project

OUTPUT FORMAT — end your response with EXACTLY this JSON block:
```json
{{
  "status": "completed",
  "agent": "{agent_name}",
  "files_written": ["<relative path>", ...],
  "summary": "<one sentence of what was implemented>"
}}
```

RULES:
- Only touch the files assigned to your task
- Never overwrite another agent's files unless explicitly told to
- If you encounter a conflict or blocker, report it in your summary
- Return concise output — do NOT dump raw file contents back
"""


def make_reviewer_prompt(project_dir: str) -> str:
    return f"""You are a code reviewer subagent in a multi-agent coding team.

Your ONLY job is to review the implemented code and report issues.

Project root on disk (for your awareness only; not for built-in file tools): {project_dir}
{VIRTUAL_FS_RULES}
For the custom tools read_file / write_file / edit_file / list_files, paths are relative to the project root.
Never use a leading `/` or `C:\\...` — on Windows that resolves outside the project and will fail.

WORKFLOW:
1. Read architecture/plan.md to understand what was planned
2. List all files to see what was implemented
3. Read each implemented file
4. Check for: correctness, completeness, consistency, missing edge cases
5. Write your review to: reviews/code_review.md

OUTPUT FORMAT — write a structured review to reviews/code_review.md:

```markdown
# Code Review

## Summary
<2-3 sentences overall assessment>

## Issues Found
### Critical (must fix)
- <file>:<line> — <issue>

### Minor (should fix)
- <file>:<line> — <issue>

## Approved Files
- <list of files that look good>

## Verdict
APPROVED / NEEDS_CHANGES
```

Return a concise summary of your review (under 150 words).
"""


def make_test_writer_prompt(project_dir: str) -> str:
    return f"""You are a test-writing subagent in a multi-agent coding team.

Your ONLY job is to write comprehensive tests for the implemented code.

Project root on disk (for your awareness only; not for built-in file tools): {project_dir}
{VIRTUAL_FS_RULES}
For the custom tools read_file / write_file / edit_file / list_files, paths are relative to the project root.
Never use a leading `/` or `C:\\...` — on Windows that resolves outside the project and will fail.

WORKFLOW:
1. Read architecture/plan.md to understand what was built
2. Read the implemented source files
3. Write pytest tests covering: happy path, edge cases, error cases
4. Save tests to the tests/ directory

TEST REQUIREMENTS:
- Import using the correct relative paths
- Cover each public function/method/class
- Include at least one edge case and one error case per function
- Use pytest fixtures where appropriate
- Tests must be runnable (no missing imports)

OUTPUT FORMAT — end with:
```json
{{
  "status": "completed",
  "agent": "test-writer",
  "test_files": ["<relative path>", ...],
  "test_count": <number of test functions written>,
  "summary": "<one sentence>"
}}
```
"""


# ---------------------------------------------------------------------------
# Build the agent team
# ---------------------------------------------------------------------------

def create_coding_team(
    project_dir: str,
    model: str = "claude-sonnet-4-6",
):
    """
    Creates a deepagents coding team.

    Architecture:
        Orchestrator (main agent)
            ├── architect subagent    → decomposes plan, writes architecture/plan.md
            ├── coder-1 subagent     → implements assigned tasks
            ├── coder-2 subagent     → implements assigned tasks (parallel)
            ├── test-writer subagent → writes tests after coders finish
            └── reviewer subagent    → reviews all code at the end

    Backend: FilesystemBackend with virtual_mode=True
        - All agents share the same project_dir
        - virtual_mode=True prevents path traversal (no ../ escapes)
        - Each agent is instructed to only touch its assigned files

    From docs:
        "StateBackend is shared between the supervisor agent and subagents"
        We use FilesystemBackend instead so files persist on real disk.
        "virtual_mode=True enables path-based access restrictions"
    """
    project_dir = str(Path(project_dir).resolve())
    Path(project_dir).mkdir(parents=True, exist_ok=True)

    # -- Backend: real filesystem, scoped to project_dir --
    # virtual_mode=True blocks ../  ~ and absolute paths outside root
    backend = FilesystemBackend(root_dir=project_dir, virtual_mode=True)

    # -- File tools for subagents --
    file_tools = make_file_tools(project_dir)

    # -- Subagent definitions --
    # CRITICAL from docs: subagents must have explicit system_prompt and tools.
    # They do NOT inherit from the main agent.
    # Descriptions must be action-oriented and specific so the main agent
    # knows exactly when to delegate.
    subagents = [
        {
            "name": "architect",
            "description": (
                "Decomposes a coding plan into atomic tasks. "
                "Use FIRST before any implementation starts. "
                "Produces architecture/plan.md with the full task breakdown."
                "Do not plan to implement any optional files or features, make the plan to include only files that are required to be implemented."
            ),
            "system_prompt": make_architect_prompt(project_dir),
            "tools": file_tools,
            "model": model,
        },
        {
            "name": "coder-1",
            "description": (
                "Implements coding tasks assigned to it. "
                "Give it a specific task from the architecture plan. "
                "It reads plan.md, implements the assigned files, and returns a completion report."
            ),
            "system_prompt": make_coder_prompt(project_dir, "coder-1"),
            "tools": file_tools,
            "model": model,
        },
        {
            "name": "coder-2",
            "description": (
                "Implements coding tasks assigned to it (runs in parallel with coder-1). "
                "Give it a DIFFERENT task than coder-1 to avoid file conflicts. "
                "It reads plan.md, implements the assigned files, and returns a completion report."
            ),
            "system_prompt": make_coder_prompt(project_dir, "coder-2"),
            "tools": file_tools,
            "model": model,
        },
        {
            "name": "coder-3",
            "description": (
                "Implements coding tasks assigned to it (runs in parallel with coder-1 and coder-2). "
                "Give it a DIFFERENT task than coder-1 and coder-2 to avoid file conflicts. "
                "It reads plan.md, implements the assigned files, and returns a completion report."
            ),
            "system_prompt": make_coder_prompt(project_dir, "coder-3"),
            "tools": file_tools,
            "model": model,
        },
        {
            "name": "test-writer",
            "description": (
                "Writes pytest tests for completed code. "
                "Use AFTER coders have finished implementing. "
                "Reads all source files and writes comprehensive tests to the tests/ directory."
            ),
            "system_prompt": make_test_writer_prompt(project_dir),
            "tools": file_tools,
            "model": model,
        },
        {
            "name": "reviewer",
            "description": (
                "Reviews all implemented code for correctness, completeness, and consistency. "
                "Use LAST after all implementation and tests are done. "
                "Writes a structured review to reviews/code_review.md."
            ),
            "system_prompt": make_reviewer_prompt(project_dir),
            "tools": file_tools,
            "model": model,
        },
    ]

    # -- Orchestrator system prompt --
    # CRITICAL from docs on "Subagent not being called":
    # "Instruct main agent to delegate" explicitly
    orchestrator_prompt = f"""You are the orchestrator of a multi-agent software engineering team.

Your job is to coordinate specialized subagents to implement a coding plan.
You do NOT write code yourself — you delegate ALL implementation work.

Project root on disk (for your awareness only; not for built-in file tools): {project_dir}
{VIRTUAL_FS_RULES}

## YOUR SUBAGENTS

- **architect**: Breaks down the plan into tasks → run FIRST
- **coder-1**, **coder-2**, **coder-3**: Implement tasks in parallel → run AFTER architect
- **test-writer**: Writes tests → run AFTER all coders finish
- **reviewer**: Reviews all code → run LAST

## WORKFLOW — follow this EXACTLY

### Phase 1: Architecture
Delegate to `architect` with the full coding plan.
Wait for it to produce architecture/plan.md before proceeding.

### Phase 2: Parallel Implementation
Read architecture/plan.md to see all tasks.
Assign DIFFERENT tasks to coder-1, coder-2, and coder-3 — never give two coders the same files.
Call `task()` for ALL coders before waiting for any results (parallel execution).
Wait for all coders to return completion reports.

### Phase 3: Testing
Delegate to `test-writer` once all coders are done.
Pass a summary of what was implemented.

### Phase 4: Review
Delegate to `reviewer` once tests are written.

### Phase 5: Final Report
After reviewer finishes, provide a FINAL REPORT:

```
## ✅ Implementation Complete

### Files implemented
- <list>

### Test coverage
- <summary>

### Review verdict
- <APPROVED / NEEDS_CHANGES>

### Next steps (if any)
- <issues to fix>
```

## CRITICAL RULES
- ALWAYS delegate using task() — never write code yourself
- NEVER give two coders the same files (causes conflicts)
- Call ALL coder tasks before waiting for results (enables parallelism)
- Only proceed to test-writer after ALL coders report completion
- Only proceed to reviewer after test-writer reports completion
- If a coder reports an error, delegate a fix to that same coder
"""

    agent = create_deep_agent(
        model=model,
        backend=backend,
        system_prompt=orchestrator_prompt,
        subagents=subagents,
        name="orchestrator",
        checkpointer=MemorySaver(),
    )

    return agent


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

async def run_coding_plan(
    plan: str,
    project_dir: str,
    model: str = "claude-haiku-4-5-20251001",
    *,
    verbose: bool = True,
) -> dict:
    """
    Run a coding plan through the multi-agent team.

    Args:
        plan: Natural language description of what to build
        project_dir: Absolute path where files will be written
        model: LLM model to use for all agents
        verbose: If True, stream tool calls and LLM tokens (including thinking blocks when
            the provider emits them) to stdout via LangGraph ``astream_events`` (v2).

    Returns:
        dict with 'output' (final report) and 'project_dir'
    """
    from langchain_core.messages import HumanMessage

    agent = create_coding_team(project_dir=project_dir, model=model)
    input_state = {"messages": [HumanMessage(content=plan)]}
    config = {"recursion_limit": 1500, "configurable": {"thread_id": f"harness-{uuid.uuid4().hex}"}}

    if not verbose:
        result = await agent.ainvoke(input_state, config)
    else:
        print("\n======== HARNESS: streaming tool calls + model tokens ========\n", flush=True)
        async for event in agent.astream_events(input_state, config, version="v2"):
            _print_harness_event(event)
        print("\n======== HARNESS: stream end ========\n", flush=True)
        snap = agent.get_state(config)
        result = dict(snap.values) if snap and snap.values is not None else {}

    # Extract final message
    final_msg = ""
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            final_msg = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    return {
        "output": final_msg,
        "project_dir": project_dir,
    }


if __name__ == "__main__":
    import asyncio

    PLAN = """
Build a full-stack todo application with a Python API client and a simple frontend.

Backend Client (Python):
- TodoClient class with methods: create_todo, get_todo, list_todos, update_todo, delete_todo
- Use httpx for async HTTP calls
- Pydantic models with full type hints
- Fields: id (str), title (str), completed (bool), created_at (datetime)
- Custom exceptions: TodoNotFoundError, TodoAPIError
- Retry logic (3 attempts) with exponential backoff

Frontend (React or simple JS app):
- UI to create, list, update, and delete todos
- Show loading + error states
- Toggle completion status
- Use fetch/axios to call backend API
- Minimal clean UI (no heavy styling required)

Testing:
- Backend tests using pytest, pytest-asyncio, httpx mock
- Basic frontend tests (optional, e.g., component rendering)

Docs:
- README with setup, API usage, and frontend run instructions
"""
    dir = os.path.join(PLAYGROUND_PATH, "todo_client")
    result = asyncio.run(run_coding_plan(
        plan=PLAN,
        project_dir=dir,
    ))

    print("\n" + "="*60)
    print("FINAL OUTPUT")
    print("="*60)
    print(result["output"])
    print(f"\nFiles written to: {result['project_dir']}")