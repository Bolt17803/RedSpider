from typing import Any, Annotated, List, TypedDict
import operator
from dotenv import load_dotenv
import os

class GraphState(TypedDict):
    '''
    this is the state dictionary containing the inital user query, architect response
    and the planner response
    '''
    title: str
    agent_node: str
    user_response: str
    architect_response: str
    planner_response: str
    final_architect_response: str
    final_planner_response: str
    architect_messages: Annotated[list, operator.add]
    planner_messages: Annotated[list, operator.add]
    code_summary: str
    validation_status: str
    validation_comments: str
    tester_status: str
    tester_comments: str
    errors: List[str]

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")


specialized_subagents = [
    {
        "name": "frontend-developer",
        "description": "Specialized in React, Vue, Angular, HTML/CSS/JavaScript frontend development",
        "system_prompt": """
        You are a frontend specialist. Create clean, modern, responsive UI code.
        Follow best practices for component architecture and state management.
        """,
        "tools": [],
        "model": f"google_genai:{GEMINI_MODEL}",
    },
    {
        "name": "backend-developer", 
        "description": "Specialized in API development, database design, server-side logic",
        "system_prompt": """
        You are a backend specialist. Create robust APIs, efficient database schemas,
        and scalable server-side logic. Follow RESTful principles and security best practices.
        """,
        "tools": [],
        "model": f"google_genai:{GEMINI_MODEL}",
    },
    {
        "name": "ml-engineer",
        "description": "Specialized in machine learning, data processing, model training",
        "system_prompt": """
        You are an ML specialist. Create efficient data pipelines, model training code,
        and inference systems. Optimize for both accuracy and performance.
        """,
        "tools": [],
        "model": f"google_genai:{GEMINI_MODEL}",
    },
    {
        "name": "devops-engineer",
        "description": "Specialized in Docker, CI/CD, deployment configurations, infrastructure",
        "system_prompt": """
        You are a DevOps specialist. Create containerization configs, CI/CD pipelines,
        deployment scripts, and infrastructure as code.
        """,
        "tools": [],
        "model": f"google_genai:{GEMINI_MODEL}",
    }
]


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
    """Execute coding agent with subagent delegation capability"""
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
                        4. Implement the missing features (delegate to subagents if complex)
                        5. Update PROJECT_SUMMARY.md when complete

                        """
        
        if state.get("tester_comments"):
            message += f"""
                        TEST FAILURE FEEDBACK:
                        {state['tester_comments']}

                        ACTION REQUIRED:
                        1. Read the error details and guidance
                        2. Use write_todos() to create tasks for each fix needed
                        3. Use read_file() to examine the problematic files
                        4. Fix the errors (delegate to specialized subagents if needed)
                        5. Update PROJECT_SUMMARY.md when complete
 
                        """
        
        message += """
                    IMPORTANT:
                    - Use read_file() to examine existing code
                    - Use edit_file() to update files
                    - Use write_todos() to track your fixes
                    - Update PROJECT_SUMMARY.md when all fixes are complete
                    """
                    # - Delegate complex fixes to specialized subagents if needed:
                    #   • task(name="frontend-developer", ...) for UI fixes
                    #   • task(name="backend-developer", ...) for API fixes
                    #   • task(name="ml-engineer", ...) for ML/data fixes
                    #   • task(name="devops-engineer", ...) for deployment fixes
    else:
        # Initial invocation
        message =  f"""
                    Implement this complete project plan:

                    {state['planner_response'][:1000]}

                    APPROACH:
                    1. Read and understand the full plan
                    2. Create a comprehensive todo list using write_todos()
                    3. Break down the project into major components
                    4. Coordinate all subagent outputs
                    5. Ensure all files are properly integrated
                    6. Create comprehensive PROJECT_SUMMARY.md with:
                    - What was implemented
                    - File structure overview
                    - Setup instructions (dependencies, env setup)
                    - Execution instructions
                    - Required environment variables and where to set them

                    
                    Start implementation now.
                    """
        
                    # 4. For each complex component, consider delegating to specialized subagents:
                    # - Frontend work → task(name="frontend-developer", task="...")
                    # - Backend APIs → task(name="backend-developer", task="...")
                    # - ML/Data pipelines → task(name="ml-engineer", task="...")
                    # - Docker/deployment → task(name="devops-engineer", task="...")
                    # - Simple tasks → Handle yourself

                    # Example subagent delegation for this OCR project:
                    # - task(name="frontend-developer", task="Create React dashboard for viewing OCR results and uploading PDFs")
                    # - task(name="backend-developer", task="Build FastAPI service with endpoints for PDF upload, processing status, and results retrieval")
                    # - task(name="ml-engineer", task="Implement complete OCR pipeline: preprocessing, OCR inference, post-processing, and WER evaluation")
                    # - task(name="devops-engineer", task="Create Docker Compose setup with all services, Redis, PostgreSQL, and proper networking")


    
    result = coder_agent.invoke({
        "messages": [{"role": "user", "content": f"this is the plan, write code for this:\n\n{state['planner_response'][:1000]}"}]
    })
    # The result object is not necessarily a string; avoid slicing it directly
    # print("--- [Coder Node] DEBUG: First invocation result ---")
    print(result)
    # print("--- [Coder Node] DEBUG: End first invocation result ---")
    
    # The coding agent will:
    # 1. Use write_todos to create task list from validation/test comments
    # 2. Delegate to subagents via task() calls
    # 3. Each subagent writes to the shared filesystem
    # 4. Main agent coordinates and creates PROJECT_SUMMARY.md
    
    # Extract summary from filesystem
    summary_result = coder_agent.invoke({
        "messages": [{"role": "user", "content": "Please read PROJECT_SUMMARY.md and return its complete contents"}]
    })
    print("--- [Coder Node] COMPLETED ---")
    print("summary result:")
    summary_text = extract_summary(summary_result)
    print(summary_text[:1000])
    return {
        "code_summary": extract_summary(summary_result),
        "agent_node": "coder",
        "validation_status": "",
        "validation_comments": "",
        "tester_status": "",
        "tester_comments": ""
    }
