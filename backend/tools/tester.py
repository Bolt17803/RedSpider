from langchain_core.tools import tool
import subprocess
import os

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
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=working_dir,
        env=env
    )
    return f"Exit Code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
