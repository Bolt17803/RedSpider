from typing import Any
from dotenv import load_dotenv
import os
from models.state import GraphState

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")

def _read_summary_from_disk(workspace_path: str) -> str:
    """
    Read PROJECT_SUMMARY.md directly from disk.
    """
    summary_path = os.path.join(workspace_path, "PROJECT_SUMMARY.md")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return f.read()
    return "PROJECT_SUMMARY.md not yet created by the coder agent."


def _extract_todos_from_result(result: Any) -> list:
    """
    Pull the last write_todos call out of the agent's tool call history
    so we can persist the final todo state into GraphState.
    We look backwards through messages to find the most recent write_todos input.
    """
    messages = []
    if isinstance(result, dict) and result.get("messages"):
        messages = result["messages"]
    elif hasattr(result, "messages"):
        messages = result.messages

    # Walk backwards — we want the LAST write_todos call, not the first
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            # Tool call blocks look like: {"type": "tool_use", "name": "write_todos", "input": {...}}
            if block.get("type") == "tool_use" and block.get("name") == "write_todos":
                raw_input = block.get("input", {})
                # Normalize: handle {"todos": [...]}, {"items": [...]}, or a plain list
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

                # Normalize "done" → "completed" to match frontend expectations
                normalized = []
                for item in todos:
                    if isinstance(item, dict):
                        norm = dict(item)
                        if norm.get("status") == "done":
                            norm["status"] = "completed"
                        normalized.append(norm)
                return normalized

    return []

def extract_summary(result) -> str:
    """
    Extract the project summary from coding agent's response.
    """
    if hasattr(result, 'messages'):
        last_message = result.messages[-1]
        content = last_message.content if hasattr(last_message, 'content') else str(last_message)
    else:
        content = str(result)
    
    return content.strip()

async def coder_node(state: GraphState, coder_agent: Any):
    """Execute coding agent — single agent handles all implementation."""
    print("--- [Coder Node] STARTED ---")
    workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])
    message = ""
    if state.get("code_summary"):
        # Re-invocation with feedback
        message = f"Previous Summary:\n{state['code_summary']}\n\n"
        
        if state.get("validation_comments") and state.get("validation_status") == "VALIDATION_INCOMPLETE":
            message += f"""
                        VALIDATION FEEDBACK:
                        {state['validation_comments']}

                        ACTION REQUIRED:
                            1. Read the validation comments carefully
                            2. Extract the "MISSING/INCOMPLETE FEATURES" section
                            3. Use write_todos() to create tasks for each missing/incomplete feature,
                            set the first task to "in_progress" and the rest to "pending"
                            4. After completing EACH individual task, immediately call write_todos() again
                            with that task's status changed to "completed" before moving to the next task.
                            The user is watching your progress in real time — this is mandatory.
                            5. Implement the missing features
                            6. Update PROJECT_SUMMARY.md when complete — do NOT create extra markdown files.
                        """
        
        message += """
                    IMPORTANT:
                    - Update PROJECT_SUMMARY.md when all fixes are complete.
                    - Do not create multiple markdown helper files.
                    - Call write_todos() after completing each task to mark it "completed".
                    
                   """
    else:
        # Initial invocation
        message =  f"""
                    Implement this complete project plan:

                    {state['planner_response']}

                    CRITICAL: Think step by step and explain the reason for each decision.

                    WORKFLOW — follow this exactly:
                        1. ls("/") to see what already exists in the workspace
                        2. Call write_todos() with ALL tasks listed. Set the first task to "in_progress"
                        and all others to "pending". This is shown live to the user.
                        3. Create the project folder structure and root config files first.
                        4. Implement each task ONE AT A TIME:
                            - Complete the task fully
                            - Then immediately call write_todos() again to mark that task "completed"
                                and set the next task to "in_progress"
                            - Only then move to the next task
                        5. This write_todos() update after EACH task is MANDATORY — the user watches
                        your progress in real time and needs to see tasks completing.
                        6. After all tasks are done, write PROJECT_SUMMARY.md with:
                            - Project overview and features
                            - Complete file structure
                            - LOCAL SETUP & RUNNING INSTRUCTIONS:
                              ⚠️ For EVERY command, specify the EXACT directory it must be run in.
                              Example: "Run `npm install` in the `/frontend` directory"
                              Example: "Run `pip install -r requirements.txt` in the `/backend` directory"
                              If frontend and backend are separate, list EACH with its own command + directory.
                            - Environment variables needed (with sample .env content and which directory)
                            - How to run the app (exact command + exact directory + expected port/URL)
                            - Build/production instructions (exact commands + directories)
                            - Deployment guide (general approach, recommended services)

                    IMPORTANT:
                        - Only create ONE markdown file: PROJECT_SUMMARY.md
                        - Do not create CONTRIBUTING.md, SETUP.md, ARCHITECTURE.md or any other .md files
                        - No deployment code unless explicitly requested
                        - Use current stable package versions — check what you know is stable in 2024/2025

                    """
        
    result = await coder_agent.ainvoke(
        {"messages": [{"role": "user", "content": message}]}
    )

    # ── Read summary directly from disk (no second agent call needed) ─────────
    summary_text = _read_summary_from_disk(workspace_path)

    # ── Extract final todo state to persist in GraphState ────────────────────
    todos = _extract_todos_from_result(result)

    print("--- [Coder Node] COMPLETED ---")

    return {
        "code_summary": summary_text,
        "todos": todos,
        "agent_node": "coder",
        "current_node": "coder_agent",
        "status": "running",
        "validation_status": "",
        "validation_comments": "",
    }
