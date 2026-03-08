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

    result = summarizer_agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
Please produce the final project summary for the user.

ORIGINAL PLAN:
{state['planner_response']}

VALIDATION COMMENTS:
{state.get('validation_comments', 'No validation comments available.')}

STEPS:
1. Use read_file() to read PROJECT_SUMMARY.md
2. Use read_file() to read validation_summary.md
3. Combine them into a single comprehensive report for the user

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
    }
