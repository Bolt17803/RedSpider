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

    # Validate working_dir
    if not os.path.exists(working_dir):
        return f"Error: Working directory '{working_dir}' does not exist."
    if not os.path.isdir(working_dir):
        return f"Error: The path '{working_dir}' is not a valid directory. Please provide a directory path, not a file path."
        
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
            
            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')
            
            error_msg = f"Error: Command timed out after 120 seconds: {command}\n\nSTDOUT (until timeout):\n{stdout}\n\nSTDERR (until timeout):\n{stderr}\n\n"
            error_msg += "HINT: This command likely started a persistent process (like a dev server or preview tool) that doesn't exit. "
            error_msg += "The test environment requires commands to terminate. Please use commands that build and exit, or run tests that finish."
            return error_msg

        
        stdout = stdout_bytes.decode('utf-8', errors='replace')
        stderr = stderr_bytes.decode('utf-8', errors='replace')
        return f"Exit Code: {process.returncode}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
