import json
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from graphs.orchestrator import graph_invoker
from langgraph.types import Command
from fastapi.responses import StreamingResponse
from typing import Any, List, Optional
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

@app.post("/workflow/start")
def start_workflow_endpoint(payload: InitRequest):
    # Use provided thread_id or generate a new one
    thread_id = payload.thread_id if payload.thread_id else str(uuid.uuid4())
    title = payload.title
    config = {"configurable": {"thread_id": thread_id}}
    init_state = {
        "user_response": payload.initial_query,
        "title": title,
        "thread_id": thread_id
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
        "thread_id": thread_id
    }


@app.post("/workflow/chat")
async def workflow_status(user_response: UserRequest):
    async def event_generator():
        config = {"configurable": {"thread_id": user_response.run_id}}
        has_streamed = False
        
        try:
            # Only emit progress for actual orchestrator graph nodes
            GRAPH_NODES = {
                "init_deepagents", "architect_agent", "architect_review",
                "planner_agent", "planner_review", "coder_agent",
                "validation_agent", "validation_approval", "summarizer_agent", "human_response"
            }
            
            # Agents whose LLM tokens + tool calls should be shown as live commentary in chat
            COMMENTARY_NODES = {"coder_agent", "validation_agent", "summarizer_agent"}
            
            # Track current top-level graph node
            current_node = "unknown"
            
            # Use astream_events to stream tokens from LLM
            async for event in graph.astream_events(
                Command(resume=user_response.query),
                config,
                version="v1",
            ):
                kind = event["event"]
                metadata = event.get("metadata", {})
                langgraph_node = metadata.get("langgraph_node", "")
                
                # Update current node from chain start events
                if kind == "on_chain_start":
                    node = langgraph_node or event.get("name", "")
                    if node and node in GRAPH_NODES:
                        current_node = node
                        yield json.dumps({"progress": node, "status": "running"}) + "\n"
                
                if kind == "on_chain_end":
                    node = langgraph_node or event.get("name", "")
                    if node and node in GRAPH_NODES:
                        yield json.dumps({"progress": node, "status": "completed"}) + "\n"
                
                # ── LLM token streaming ──────────────────────────────────────────
                if kind == "on_chat_model_stream":
                    tags = event.get("tags", [])
                    chunk_content = event["data"]["chunk"].content
                    
                    # Extract ONLY plain text — skip tool_use / input_json_delta objects
                    # Anthropic sends chunk_content as a list of typed blocks when streaming
                    # tool calls. We must discard those and only surface text.
                    def _text_only(content) -> str:
                        if isinstance(content, str):
                            return content
                        if isinstance(content, list):
                            parts = []
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") in ("text", "text_delta", "thinking"):
                                        parts.append(item.get("text", ""))
                                    # Intentionally skip tool_use, input_json_delta, etc.
                                elif isinstance(item, str):
                                    parts.append(item)
                            return "".join(parts)
                        return ""
                    
                    if "planner_stream" in tags:
                        text = _text_only(chunk_content)
                        if text:
                            has_streamed = True
                            yield json.dumps({"token": text}) + "\n"
                    
                    elif current_node in COMMENTARY_NODES:
                        text = _text_only(chunk_content)
                        if text:
                            has_streamed = True
                            yield json.dumps({
                                "type": "agent_token",
                                "node": current_node,
                                "content": text
                            }) + "\n"
                
                # ── Tool call streaming ──────────────────────────────────────────
                if kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    tool_input = event["data"].get("input", {})
                    
                    if tool_name == "execute_command":
                        # Keep existing terminal_log behaviour for execute_command
                        cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else str(tool_input)
                        wdir = tool_input.get("working_dir", "") if isinstance(tool_input, dict) else ""
                        yield json.dumps({
                            "terminal_log": f"🔧 Executing: {cmd}\n   In: {wdir}\n",
                            "type": "command_start"
                        }) + "\n"
                    elif current_node in COMMENTARY_NODES and tool_name:
                        # Only emit the tool name — suppress args to avoid dumping code/files
                        yield json.dumps({
                            "type": "agent_tool_start",
                            "node": current_node,
                            "tool": tool_name,
                            "args": {}
                        }) + "\n"
                
                if kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    output = event["data"].get("output", "")
                    
                    if tool_name == "execute_command":
                        # Keep existing terminal_log behaviour for execute_command
                        yield json.dumps({
                            "terminal_log": f"{output}\n",
                            "type": "command_end"
                        }) + "\n"
                    elif current_node in COMMENTARY_NODES and tool_name:
                        # Only emit tool name and a simple done marker — no output content
                        yield json.dumps({
                            "type": "agent_tool_end",
                            "node": current_node,
                            "tool": tool_name,
                            "output": "\u2713 done"
                        }) + "\n"
            
            # After streaming ends, get the current state to check for interrupts
            current_state = graph.get_state(config)
            state_values = current_state.values
            
            print(f"[Chat] State values keys: {state_values.keys() if state_values else 'None'}")
            print(f"[Chat] Has streamed: {has_streamed}")
            
            # Check if there's an interrupt (architect/planner review OR tester command approval)
            if current_state.next:
                if hasattr(current_state, 'tasks') and current_state.tasks:
                    for task in current_state.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            interrupt_value = task.interrupts[0].value
                            agent_node = state_values.get('agent_node', 'unknown')
                            
                            # Check if this is a command approval interrupt from tester
                            interrupt_type = interrupt_value.get('type', '') if isinstance(interrupt_value, dict) else ''
                            
                            if interrupt_type == 'command_approval':
                                instruction = interrupt_value.get('instruction', '')
                                content_to_review = interrupt_value.get('content_to_review', '')
                                
                                print(f"[Chat] Command approval interrupt from {current_node} - command: {content_to_review[:100]}")
                                
                                yield json.dumps({
                                    "token": instruction,
                                    "agent_node": current_node,  # dynamic: tester_agent OR validation_agent
                                    "instruction": "Type 'approve' to run the command or 'reject' to skip it.",
                                    "is_interrupt": True,
                                    "interrupt_type": "command_approval"
                                }) + "\n"
                            else:
                                # Regular interrupt (architect/planner review)
                                content_to_review = interrupt_value.get('content_to_review')
                                instruction = interrupt_value.get('instruction')
                                
                                print(f"[Chat] Found interrupt - agent: {agent_node}, content length: {len(content_to_review) if content_to_review else 0}")
                                
                                if content_to_review:
                                    yield json.dumps({
                                        "token": content_to_review,
                                        "agent_node": agent_node,
                                        "instruction": instruction,
                                        "is_interrupt": True
                                    }) + "\n"
                            break
            else:
                # No interrupt — send completion signal
                agent_node = state_values.get('agent_node', 'unknown') if state_values else 'unknown'
                yield json.dumps({
                    "done": True,
                    "agent_node": agent_node
                }) + "\n"

        except Exception as e:
            print(f"Error in stream: {e}")
            import traceback
            traceback.print_exc()
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
