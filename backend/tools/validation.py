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