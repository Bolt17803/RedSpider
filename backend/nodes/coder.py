from typing import Any
from dotenv import load_dotenv
import os
from models.state import GraphState

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
# PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")

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

def coder_node(state: GraphState, coder_agent: Any):
    """Execute coding agent — single agent handles all implementation."""
    print("--- [Coder Node] STARTED ---")
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
                        3. Use write_todos() to create tasks for each missing/incomplete feature
                        4. Implement the missing features
                        5. Update PROJECT_SUMMARY.md when complete, do not create multiple markdown helper files.

                        """
        
        # if state.get("tester_comments"):
        #     message += f"""
        #                 TEST FAILURE FEEDBACK:
        #                 {state['tester_comments']}

        #                 ACTION REQUIRED:
        #                 1. Read the error details and guidance
        #                 2. Use write_todos() to create tasks for each fix needed
        #                 3. Use read_file() to examine the problematic files
        #                 4. Fix the errors
        #                 5. Update PROJECT_SUMMARY.md when complete
 
        #                 """
        
        message += """
                    IMPORTANT:
                    - Update PROJECT_SUMMARY.md when all fixes are complete do not create multiple markdown helper files.
                    
                   """
    else:
        # Initial invocation
        message =  f"""
                    Implement this complete project plan:

                    {state['planner_response']}

                    CRITICAL: Think step by step and explain the reason of taking a particular decision

                    IMPORTANT:
                    - Ensure all files are properly integrated.
                    - Only a single PROJECT_SUMMARY.md should be created to write all summaries.
                    - Create comprehensive PROJECT_SUMMARY.md with these sections:
                        -> What was implemented (project overview, features, tech stack, system architecture)
                        -> File structure overview
                        -> Setup instructions (dependencies, env setup)
                        -> Execution instructions
                        -> Required environment variables and where to set them
                    
                    Start implementation now.
                    """
        
    result = coder_agent.invoke(
        {"messages": [{"role": "user", "content": message}]}
    )
    
    # summary_path = os.path.join(workspace_path, "PROJECT_SUMMARY.md")

    # if os.path.exists(summary_path):
    #     with open(summary_path, "r") as f:
    #         summary_text = f.read()
    # else:
    #     summary_text = "Summary not generated yet. Coder agent yet to create PROJECT_SUMMARY.md"
    # Extract summary from filesystem
    summary_result = coder_agent.invoke({
        "messages": [{"role": "user", "content": "Please read PROJECT_SUMMARY.md and return its complete contents"}]
    })
    print("--- [Coder Node] COMPLETED ---")
    # print("summary result:")
    summary_text = extract_summary(summary_result)
    # print(summary_text[:1000])
    return {
        "code_summary": summary_text,
        "agent_node": "coder",
        "validation_status": "",
        "validation_comments": "",
        "tester_status": "",
        "tester_comments": ""
    }
