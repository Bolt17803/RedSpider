"""
Standalone tester agent runner — directly test the tester agent
against an existing project without running the full workflow.

Usage:
    python test_tester.py <project_folder_name>
    
Example:
    python test_tester.py TOdo_app

This will invoke the tester agent against:
    backend/data/playground/<project_folder_name>
"""

import os
import sys
import json
from dotenv import load_dotenv
from pathlib import Path
from langgraph.types import Command

load_dotenv()

# Setup paths
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL")

def run_tester(project_name: str):
    from langchain_anthropic import ChatAnthropic
    from deepagents import create_deep_agent
    from deepagents.backends import FilesystemBackend
    from langchain.agents.middleware import HumanInTheLoopMiddleware
    from langchain.agents.structured_output import ProviderStrategy
    from langgraph.checkpoint.memory import MemorySaver
    from tools.tester import execute_command
    from prompts.tester import tester_backstory
    from pydantic import BaseModel, Field
    from typing import Literal
    
    class TesterResult(BaseModel):
        """Structured output from the tester agent."""
        test_status: Literal["PASS", "FAIL", "IN_PROGRESS"] = Field(
            description="Overall test status: PASS if all tests pass, FAIL if any test fails, IN_PROGRESS if testing is incomplete"
        )
        comments: str = Field(
            description="Detailed test results, error descriptions, or command output summary"
        )
    
    project_path = os.path.join(PLAYGROUND_PATH, project_name)
    
    if not os.path.isdir(project_path):
        print(f"❌ Project directory not found: {project_path}")
        print(f"Available projects in {PLAYGROUND_PATH}:")
        for d in os.listdir(PLAYGROUND_PATH):
            if os.path.isdir(os.path.join(PLAYGROUND_PATH, d)):
                print(f"  - {d}")
        return
    
    print(f"🧪 Tester Agent — Direct Runner")
    print(f"{'='*60}")
    print(f"Project: {project_name}")
    print(f"Path:    {project_path}")
    print(f"Model:   {ANTHROPIC_MODEL}")
    print(f"{'='*60}\n")
    
    # Create the tester agent (same as orchestrator.py)
    llm = ChatAnthropic(
        model=ANTHROPIC_MODEL,
        temperature=0.1
    )
    
    root_dir = str(Path(project_path).resolve())
    backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    
    tester_agent = create_deep_agent(
        model=llm,
        system_prompt=tester_backstory(),
        tools=[execute_command],
        backend=backend,
        checkpointer=MemorySaver(),
        response_format=ProviderStrategy(TesterResult),
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={"execute_command": True},
                description_prefix="Approve this command execution:"
            )
        ]
    )
    
    inner_config = {"configurable": {"thread_id": f"test-{project_name}"}}
    
    # Read code summary from project if available
    code_summary = "No summary available — explore the project files to understand it."
    for md_file in ["START_HERE.md", "README.md", "CODE_SUMMARY.md"]:
        md_path = os.path.join(project_path, md_file)
        if os.path.exists(md_path):
            with open(md_path, 'r', encoding='utf-8') as f:
                code_summary = f.read()[:3000]
            print(f"📄 Loaded summary from {md_file}")
            break
    
    # Track how many messages we've already printed
    printed_msg_count = 0
    
    def _print_tool_outputs(result, start_from=0):
        """Print tool call outputs (command results) from agent messages."""
        messages = []
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
        elif hasattr(result, 'messages'):
            messages = result.messages
        
        for i, msg in enumerate(messages):
            if i < start_from:
                continue
            msg_type = type(msg).__name__
            if msg_type == "ToolMessage":
                tool_name = getattr(msg, 'name', 'unknown')
                content = getattr(msg, 'content', str(msg))
                if tool_name == "execute_command":
                    print(f"\n{'─'*60}")
                    print(f"📟 COMMAND OUTPUT ({tool_name}):")
                    print(f"{'─'*60}")
                    print(content[:3000])
                    print(f"{'─'*60}")
            elif msg_type == "AIMessage":
                # Show tool calls the AI is making
                tool_calls = getattr(msg, 'tool_calls', [])
                for tc in tool_calls:
                    if tc.get('name') == 'execute_command':
                        args = tc.get('args', {})
                        print(f"\n🔧 Agent calling: {args.get('command', '?')}")
                        print(f"   in: {args.get('working_dir', '?')}")
        
        return len(messages)
    
    print(f"\n🚀 Invoking tester agent...\n")
    
    # Initial invocation
    result = tester_agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
Test this implementation and provide detailed feedback for the coding agent.

⚠️ CRITICAL — PATH RULES:
- For ls(), read_file(), write_file(): ALWAYS use VIRTUAL paths starting with "/"
  Example: ls("/"), read_file("/src/app.py")
  NEVER pass Windows absolute paths (like C:\\...) to these tools!

- For execute_command(): The root workspace is: {project_path}
  You MUST first explore with ls("/") to find which subdirectory contains the actual project files (e.g. package.json, requirements.txt, Makefile).
  Then use the FULL ABSOLUTE path to that subdirectory as working_dir in execute_command.
  For example if ls("/") shows a "todo-app" folder with package.json, use:
  working_dir="{project_path}\\todo-app"

STEPS:
1. Use ls("/") to explore the project structure and find the main app directory
2. Read key files (package.json, README.md, etc.) using read_file() with virtual paths
3. Determine the correct subdirectory for running commands
4. Use execute_command with working_dir set to the correct absolute path

CODE SUMMARY:
{code_summary}
"""
        }]
    }, inner_config)
    
    printed_msg_count = _print_tool_outputs(result, printed_msg_count)
    
    # Interrupt loop — handle HITL command approvals in the terminal
    while True:
        inner_state = tester_agent.get_state(inner_config)
        
        if not inner_state.next:
            print("\n✅ Tester agent finished (no more interrupts)")
            break
        
        # Find the interrupt
        hitl_request = None
        if hasattr(inner_state, 'tasks') and inner_state.tasks:
            for task in inner_state.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    hitl_request = task.interrupts[0].value
                    break
        
        if hitl_request is None:
            print("\n✅ No interrupt found — agent finished")
            break
        
        # Display the command for approval
        action_requests = getattr(hitl_request, "action_requests", [])
        if not action_requests and isinstance(hitl_request, dict):
            action_requests = hitl_request.get("action_requests", [])
        
        num_actions = len(action_requests)
        
        print(f"\n{'='*60}")
        print(f"🔧 COMMAND APPROVAL NEEDED ({num_actions} action(s))")
        print(f"{'='*60}")
        
        for i, req in enumerate(action_requests, 1):
            name = getattr(req, "name", None) or (req.get("name") if isinstance(req, dict) else "?")
            args = getattr(req, "args", None) or (req.get("args", {}) if isinstance(req, dict) else {})
            
            if name == "execute_command":
                print(f"  Command {i}: {args.get('command', '?')}")
                print(f"  Dir:       {args.get('working_dir', '?')}")
            else:
                print(f"  Tool {i}: {name}({json.dumps(args, default=str)})")
        
        print(f"{'='*60}")
        
        # Ask user in terminal
        user_input = input("  → approve / reject [approve]: ").strip().lower()
        if not user_input:
            user_input = "approve"
        
        decision_type = "approve" if user_input in ("approve", "yes", "y", "") else "reject"
        decisions = [{"type": decision_type} for _ in range(num_actions)]
        
        print(f"  ✔ Sending {len(decisions)} decision(s): {decision_type}\n")
        
        result = tester_agent.invoke(
            Command(resume={"decisions": decisions}),
            inner_config,
        )
        
        printed_msg_count = _print_tool_outputs(result, printed_msg_count)
    
    # Show final result
    print(f"\n{'='*60}")
    print(f"📋 TESTER RESULT")
    print(f"{'='*60}")
    print(f"Result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
    
    if isinstance(result, dict) and "structured_response" in result:
        sr = result["structured_response"]
        print(f"\n✅ STRUCTURED OUTPUT:")
        print(f"  test_status: {sr.test_status}")
        print(f"  comments:    {sr.comments[:2000]}")
    else:
        # Fallback
        if isinstance(result, dict) and "messages" in result:
            content = result["messages"][-1].content if result["messages"] else str(result)
        elif hasattr(result, 'messages') and result.messages:
            content = result.messages[-1].content
        else:
            content = str(result)
        print(f"\n📝 RAW OUTPUT (no structured_response):")
        print(content[:3000])
    
    print(f"{'='*60}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_tester.py <project_folder_name>")
        print("Example: python test_tester.py TOdo_app")
        
        # List available projects
        if os.path.isdir(PLAYGROUND_PATH):
            print(f"\nAvailable projects in {PLAYGROUND_PATH}:")
            for d in os.listdir(PLAYGROUND_PATH):
                if os.path.isdir(os.path.join(PLAYGROUND_PATH, d)):
                    print(f"  - {d}")
        sys.exit(1)
    
    run_tester(sys.argv[1])
