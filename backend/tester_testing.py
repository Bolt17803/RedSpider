
from deepagents.backends import FilesystemBackend
from langchain_core.tools import tool
import subprocess
import os
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
load_dotenv()
from deepagents import create_deep_agent
from prompts.tester import tester_backstory

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL")
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")

deepagent_llm = ChatAnthropic(
    model=ANTHROPIC_MODEL,
    temperature=0.3,
)

@tool
def execute_command(command: str, working_dir: str, env_vars: dict) -> str:
    """Execute a shell command with specified environment variables
    args:
        command: The command to execute
        working_dir: The directory to execute the command in
        env_vars: Environment variables to set for the command
    """
    env = os.environ.copy()
    env.update(env_vars)

    # Validate working_dir
    if not os.path.exists(working_dir):
        return f"Error: Working directory '{working_dir}' does not exist."
    if not os.path.isdir(working_dir):
        return f"Error: The path '{working_dir}' is not a valid directory. Please provide a directory path, not a file path."
        
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=working_dir,
            env=env
        )
        return f"Exit Code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
    return f"Exit Code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"

root_dir = os.path.join(PLAYGROUND_PATH, "test44", "project")

backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)

tester_agent = create_deep_agent(
        model=deepagent_llm,
        system_prompt=tester_backstory(),
        tools = [execute_command],
        backend=backend
    )
print("---------------AGENT INITIALIZED--------------")
result = tester_agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
Test this implementation and provide detailed feedback for the coding agent.

FOR CODE SUMMARY CHECK THE MARKDOWN FILES IN THE PROJECT FOLDER
"""
        }]
    })
    
test_result = extract_test_result(result)
print("--- [Tester Node] COMPLETED ---")
print("test result:")
print(test_result)
# print({"tester_status": test_result["status"],
#     "tester_comments": test_result["comments"],
#     "agent_node": "tester"
# })