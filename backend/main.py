import json
import uuid
import time
from dataclasses import dataclass
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from graphs.orchestrator import graph_invoker
from langgraph.types import Command
from fastapi.responses import StreamingResponse
from typing import Any, List, Optional, AsyncGenerator
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
import re
import ast

graph: Any = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],  # Next.js and Streamlit
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InitRequest(BaseModel):
    initial_query: str
    title: str
    thread_id: Optional[str] = None

class UserRequest(BaseModel):
    run_id: str
    query: str

import sqlite3

@app.on_event("startup")
def startup_event():
    global graph 
    # User requested MemorySaver (in-memory storage only)
    graph = graph_invoker()
    img_bytes = graph.get_graph().draw_mermaid_png()
    with open("graph.png", "wb") as f:
        f.write(img_bytes)


@app.get("/")
def read_root():
    return {"Hello": "World"}

import csv
import os
load_dotenv()

PROJECTS_CSV_PATH = os.getenv("PROJECTS_CSV_PATH")
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")

# Ensure directory exists
os.makedirs(os.path.dirname(PROJECTS_CSV_PATH), exist_ok=True)

# Initialize Virtual File System
from vfs import LocalFileSystemProvider
vfs_provider = LocalFileSystemProvider(PLAYGROUND_PATH)

class CreateProjectRequest(BaseModel):
    title: str
    thread_id: str


@app.post('/create-project')
def create_project(project: CreateProjectRequest):
    file_exists = os.path.isfile(PROJECTS_CSV_PATH)
    with open(PROJECTS_CSV_PATH, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['title', 'id'])
        writer.writerow([project.title, project.thread_id])
    workdir_path = os.path.join(PLAYGROUND_PATH, project.title)
    if not os.path.exists(workdir_path):
        os.makedirs(workdir_path)

    return {"message": "Project created successfully"}

@app.get("/projects-history")
def get_projects():
    if not os.path.exists(PROJECTS_CSV_PATH):
        return {"projects": []}
    
    projects = []
    try:
        with open(PROJECTS_CSV_PATH, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Strip spaces from keys if present in CSV
                clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
                if 'title' in clean_row and 'id' in clean_row:
                    projects.append(clean_row)
    except Exception as e:
        print(f"Error reading projects CSV: {e}")
        return {"projects": []}
        
    return {"projects": projects}

@app.get("/workspace/tree/{project_id}")
def get_workspace_tree(project_id: str):
    """Returns the JSON hierarchical directory tree for a project."""
    try:
        tree = vfs_provider.get_tree(project_id)
        return {"tree": tree}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workspace/file/{project_id}")
def get_workspace_file(project_id: str, path: str):
    """Returns the raw content of a specific file in the project."""
    try:
        content = vfs_provider.get_file_content(project_id, path)
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/start")
def start_workflow_endpoint(payload: InitRequest):
    # Use provided thread_id or generate a new one
    thread_id = payload.thread_id if payload.thread_id else str(uuid.uuid4())
    title = payload.title
    config = {"configurable": {"thread_id": thread_id}}
    init_state = {
        "user_response": payload.initial_query,
        "title": title,
        "thread_id": thread_id,
        "status": "running",
        "current_node": None,
        "todos": [],
        "errors": [],
    }
    intermediate_state = graph.invoke(init_state, config)

    if '__interrupt__' in intermediate_state:
        interrupt_data = intermediate_state['__interrupt__']
        interrupt_value = interrupt_data[0].value
        agent_output = interrupt_value['content_to_review']
        agent_instruction = interrupt_value['instruction']
        agent_node = intermediate_state.get('agent_node', 'unknown')
    else:
        agent_output = None
        agent_instruction = None
        agent_node = intermediate_state.get('agent_node', 'unknown')
        
    return {
        "agent_output": agent_output, 
        "agent_instruction": agent_instruction, 
        "thread_id": thread_id, 
        "agent_node": agent_node
    }

@app.get("/workflow/state/{thread_id}")
def get_workflow_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        current_state = graph.get_state(config)
    except Exception as e:
        # Return empty state if thread not found (not started yet)
        return {"messages": [], "not_started": True}

    if not current_state or not current_state.values:
        return {"messages": [], "not_started": True}

    state_values = current_state.values
    if not state_values:
        return {"messages": [], "not_started": True}

    # Extract active node and instruction if interrupted
    active_node = state_values.get('agent_node', None)
    instruction = None
    
    # Check for interrupts
    if current_state.tasks:
        for task in current_state.tasks:
            if hasattr(task, 'interrupts') and task.interrupts:
                interrupt_value = task.interrupts[0].value
                instruction = interrupt_value.get('instruction')

    # Collect messages history
    frontend_messages = []
    
    # helper to process message list
    def format_structured_architect_response(content):
        # Check if content starts with the specific prefix
        prefix = "Returning structured response: "
        if not content.startswith(prefix):
            return content
        
        try:
            # Clean content for parsing
            clean_content = content[len(prefix):]
            
            # Extract project_goals
            goals_match = re.search(r"project_goals=(\[.*?\])", clean_content, re.DOTALL)
            questions_match = re.search(r"follow_up_questions=(\[.*?\])", clean_content, re.DOTALL)
            
            formatted_response = ""
            
            # Format Goals
            if goals_match:
                goals_list = ast.literal_eval(goals_match.group(1))
                formatted_response += "## Project Goals\n"
                if goals_list:
                    for i, goal in enumerate(goals_list, 1):
                        formatted_response += f"{i}. {goal}\n"
                else:
                    formatted_response += "project goals are not properly defined. Answer the below follow-up questions\n"
            
            formatted_response += "\n"
            
            # Format Questions
            if questions_match:
                questions_list = ast.literal_eval(questions_match.group(1))
                formatted_response += "## Follow-up Questions\n"
                if questions_list:
                    for i, question in enumerate(questions_list, 1):
                        formatted_response += f"{i}. {question}\n"
                else:
                    formatted_response += "No follow-up questions.\n"
            
            if not formatted_response.strip():
                return content # Fallback if parsing found nothing
                
            return formatted_response
            
        except Exception as e:
            print(f"Error parsing structured response: {e}")
            return content

    def process_msgs(msgs, node_name):
        for m in msgs:
            # print(f"Processing message: type={type(m)}, content={m.content[:20]}...")
            role = 'user' if isinstance(m, HumanMessage) else 'agent'
            
            content = m.content
            if node_name == 'architect_agent' and role == 'agent':
                content = format_structured_architect_response(content)

            frontend_messages.append({
                "role": role,
                "content": content,
                "node": node_name
            })

    # Add Architect messages
    if 'architect_messages' in state_values:
        process_msgs(state_values['architect_messages'], 'architect_agent')

    # Add Planner messages
    if 'planner_messages' in state_values:
        process_msgs(state_values['planner_messages'], 'planner_agent')

    # Note: This simply concatenates lists. A real timestamps-based implementation
    # would merge them sorted by time. For now, we assume architect runs first.
    
    return {
        "messages": frontend_messages,
        "active_node": active_node,
        "instruction": instruction,
        "thread_id": thread_id,
        "status": state_values.get("status", "idle"),
        "current_node": state_values.get("current_node", None),
        "todos": state_values.get("todos", []),
    }

import time as _time

# Human-readable labels for deep agent nodes
NODE_LABELS = {
    "coder_agent": "Coder",
    "validation_agent": "Validator",
    "summarizer_agent": "Summarizer",
}

@dataclass
class NodeGroups:
    progress_nodes: frozenset = frozenset([
        "init_deepagents", "architect_agent", "architect_review",
        "planner_agent", "planner_review", "coder_agent",
        "validation_agent", "validation_approval", "summarizer_agent", "human_response"
    ])
    commentary_nodes: frozenset = frozenset(["coder_agent", "validation_agent", "summarizer_agent"])

class EventHandlers:
    CHAIN_START = "on_chain_start"
    CHAIN_END = "on_chain_end"
    LLM_STREAM = "on_chat_model_stream"
    TOOL_START = "on_tool_start"
    TOOL_END = "on_tool_end"

def _extract_text(chunk_content: any) -> str:
    """Extract plain text from Anthropic chunk (handles str/list/dict).
    Intentionally skips tool_use, input_json_delta, and other non-text blocks.
    """
    if isinstance(chunk_content, str):
        return chunk_content
    if isinstance(chunk_content, list):
        parts = []
        for item in chunk_content:
            if isinstance(item, dict):
                if item.get("type") in ("text", "text_delta", "thinking"):
                    parts.append(item.get("text", ""))
                # Intentionally skip tool_use, input_json_delta, etc.
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""

def _extract_todos(data: any) -> list | None:
    """Extract a todos list from write_todos tool input or output.
    Handles: list directly, {'todos': [...]}, {'items': [...]}, or any dict with a list value.
    Normalizes 'done' status to 'completed' to match frontend interface.
    """
    todos = None
    try:
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, list):
            todos = data
        elif isinstance(data, dict):
            # Try common keys first
            for key in ("todos", "items", "tasks"):
                if key in data and isinstance(data[key], list):
                    todos = data[key]
                    break
            # Last resort: first list value in the dict
            if todos is None:
                for v in data.values():
                    if isinstance(v, list):
                        todos = v
                        break
    except (json.JSONDecodeError, TypeError):
        pass
    
    if todos is None:
        return None
    
    # Normalize status: deepagents uses 'done' but frontend expects 'completed'
    normalized = []
    for item in todos:
        if isinstance(item, dict):
            norm = dict(item)
            if norm.get("status") == "done":
                norm["status"] = "completed"
            normalized.append(norm)
        else:
            normalized.append(item)
    return normalized

def handle_event(event: dict, state: dict, nodes: NodeGroups) -> list[str]:
    """Unified event handler — returns list of SSE strings."""
    kind = event["event"]
    metadata = event.get("metadata", {})
    # IMPORTANT: For node lifecycle (chain_start/chain_end), use event["name"]
    # which is the actual runnable name. metadata["langgraph_node"] is set on ALL
    # events inside a node (inner LLM calls, tool calls, etc.) and must NOT be
    # used to detect the outer graph node start/end.
    event_name = event.get("name", "")
    langgraph_node = metadata.get("langgraph_node", "")
    events = []
    
    # Node lifecycle — only match the OUTER graph node, not inner runnables
    if kind == EventHandlers.CHAIN_START and event_name in nodes.progress_nodes:
        state["current_node"] = event_name
        events.append(json.dumps({"progress": event_name, "status": "running"}) + "\n")
        # Emit subagent_start for deep agent nodes
        if event_name in nodes.commentary_nodes:
            state["active_deep_agent"] = event_name
            state.setdefault("start_times", {})[event_name] = _time.time()
            events.append(json.dumps({
                "type": "subagent_start",
                "node": event_name,
                "label": NODE_LABELS.get(event_name, event_name),
                "startedAt": int(_time.time() * 1000),
            }) + "\n")
    
    elif kind == EventHandlers.CHAIN_END and event_name in nodes.progress_nodes:
        events.append(json.dumps({"progress": event_name, "status": "completed"}) + "\n")
        # Emit subagent_end for deep agent nodes
        if event_name in nodes.commentary_nodes:
            state["active_deep_agent"] = None  # clear active tracker
            events.append(json.dumps({
                "type": "subagent_end",
                "node": event_name,
                "label": NODE_LABELS.get(event_name, event_name),
                "status": "complete",
                "completedAt": int(_time.time() * 1000),
            }) + "\n")
    
    # LLM streaming — use langgraph_node (from metadata) to route tokens
    # Falls back to active_deep_agent when inner agent nodes stream (langgraph_node='agent')
    elif kind == EventHandlers.LLM_STREAM:
        tags = event.get("tags", [])
        text = _extract_text(event["data"]["chunk"].content)
        if text:
            state["has_streamed"] = True
            if "planner_stream" in tags:
                events.append(json.dumps({"token": text}) + "\n")
            else:
                target_node = langgraph_node if langgraph_node in nodes.commentary_nodes else state.get("active_deep_agent")
                if target_node:
                    events.append(json.dumps({
                        "type": "agent_token", "node": target_node, "content": text
                    }) + "\n")
    
    # Tool calls
    elif kind == EventHandlers.TOOL_START:
        tool_name = event_name
        tool_input = event["data"].get("input", {})
        tool_node = langgraph_node if langgraph_node in nodes.commentary_nodes else state.get("active_deep_agent")
        if tool_name == "execute_command":
            cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else str(tool_input)
            wdir = tool_input.get("working_dir", "") if isinstance(tool_input, dict) else ""
            events.append(json.dumps({
                "terminal_log": f"🔧 Executing: {cmd}\n   In: {wdir}\n", "type": "command_start"
            }) + "\n")
        elif tool_name == "write_todos":
            # Emit todo_update from TOOL_START using the INPUT (not output)
            # The tool output is typically just a success confirmation string
            todos = _extract_todos(tool_input)
            if todos is not None and tool_node:
                events.append(json.dumps({
                    "type": "todo_update",
                    "node": tool_node,
                    "todos": todos,
                }) + "\n")
            if tool_node:
                events.append(json.dumps({
                    "type": "agent_tool_start", "node": tool_node,
                    "tool": tool_name, "args": {}
                }) + "\n")
        elif tool_node and tool_name:
            events.append(json.dumps({
                "type": "agent_tool_start", "node": tool_node,
                "tool": tool_name, "args": {}
            }) + "\n")
    
    elif kind == EventHandlers.TOOL_END:
        tool_name = event_name
        output = event["data"].get("output", "")
        tool_node = langgraph_node if langgraph_node in nodes.commentary_nodes else state.get("active_deep_agent")
        if tool_name == "execute_command":
            events.append(json.dumps({"terminal_log": f"{output}\n", "type": "command_end"}) + "\n")
        elif tool_node and tool_name:
            events.append(json.dumps({
                "type": "agent_tool_end", "node": tool_node,
                "tool": tool_name, "output": "✔ done"
            }) + "\n")
    
    return events

def handle_interrupt(state, current_node: str) -> list[str]:
    """Simplified interrupt handler."""
    for task in getattr(state, 'tasks', []):
        interrupt = getattr(task, 'interrupts', [None])[0]
        if not interrupt:
            continue
            
        interrupt_value = interrupt.value
        interrupt_type = interrupt_value.get('type', '') if isinstance(interrupt_value, dict) else ''
        
        if interrupt_type == 'command_approval':
            return [json.dumps({
                "token": interrupt_value.get('instruction', ''),
                "agent_node": current_node,
                "instruction": "Type 'approve' to run or 'reject' to skip.",
                "is_interrupt": True, "interrupt_type": "command_approval"
            }) + "\n"]
        else:
            # Architect/planner review
            content = interrupt_value.get('content_to_review', '')
            return [json.dumps({
                "token": content, "agent_node": current_node,
                "instruction": interrupt_value.get('instruction', ''),
                "is_interrupt": True
            }) + "\n"]
    return []

@app.post("/workflow/chat")
async def workflow_status(user_response: UserRequest):
    async def event_generator() -> AsyncGenerator[str, None]:
        config = {"configurable": {"thread_id": user_response.run_id}}
        state_tracker = {"current_node": "unknown", "has_streamed": False}
        node_groups = NodeGroups()

        try:
            async for event in graph.astream_events(
                Command(resume=user_response.query),
                config,
                version="v2",
            ):
                for chunk in handle_event(event, state_tracker, node_groups):
                    yield chunk

            # After the stream ends, check final state
            current_state = graph.get_state(config)

            if not current_state.next:
                # Graph reached END — emit explicit completion event
                # The frontend should listen for type="workflow_complete"
                # rather than inferring from stream closure (which is a race condition)
                final_status = current_state.values.get("status", "completed")
                yield json.dumps({
                    "type": "workflow_complete",
                    "done": True,
                    "status": final_status,
                    "agent_node": current_state.values.get("agent_node", "unknown"),
                    "current_node": current_state.values.get("current_node", None),
                    "todos": current_state.values.get("todos", []),
                }) + "\n"
            else:
                # Graph is paused at an interrupt — emit interrupt details
                for chunk in handle_interrupt(current_state, state_tracker["current_node"]):
                    yield chunk

        except Exception as e:
            print(f"[workflow/chat] Error: {e}")
            yield json.dumps({"type": "error", "error": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
