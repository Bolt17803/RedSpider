from typing import Any
import os
from dotenv import load_dotenv
from models.state import GraphState

load_dotenv()

PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")


def extract_summary(result) -> str:
    """Extract text content from agent result."""
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

    return content.strip()


def summarizer_node(state: GraphState, summarizer_agent: Any):
    """Read PROJECT_SUMMARY.md and validation_summary.md, then produce a final user-facing summary."""
    print("--- [Summarizer Node] STARTED ---")

    validation_status = state.get('validation_status', 'unknown')
    validation_comments = state.get('validation_comments', 'No validation comments available.')

    result = summarizer_agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
Please produce the final project report for the user.

ORIGINAL PLAN:
{state['planner_response']}

VALIDATION STATUS: {validation_status}

VALIDATION COMMENTS:
{validation_comments}

YOUR STEPS — follow this exactly:
1. Use read_file("/PROJECT_SUMMARY.md") to read the coder's project documentation.
   This file contains the setup instructions, file structure, and run commands.
   
2. Use read_file("/validation_summary.md") to read the validation results.
   This file contains what the validation agent checked and any issues found.

3. Combine BOTH files with the original plan into a single comprehensive report.

4. The report MUST include:
   - Project overview and features implemented
   - Complete file structure
   - DETAILED step-by-step local setup & run instructions
     (copy exact commands and directories from PROJECT_SUMMARY.md)
   - Environment variables needed and where to get them
   - Validation results summary
   - Any additional steps the user needs to take (external packages, API keys, etc.)
   - Suggested next steps / improvements

⚠️ The "How to Set Up & Run Locally" section is the MOST IMPORTANT part.
The user needs exact commands with exact directories to get the project running.

If a file doesn't exist, note it and work with the information you have.
"""
        }]
    })

    summary_text = extract_summary(result)
    print("--- [Summarizer Node] COMPLETED ---")
    print(summary_text[:1000])

    return {
        "final_summary": summary_text,
        "agent_node": "summarizer_agent",
        "status": "completed"
    }
