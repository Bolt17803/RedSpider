from typing import Any
from dotenv import load_dotenv
import os
from models.state import GraphState

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")


specialized_subagents = [
    {
        "name": "frontend-developer",
        "description": "Expert in modern frontend architecture using React, Vue, Angular, TypeScript, HTML, CSS, and performance optimization",
        "system_prompt": """
You are a senior frontend architect building production-grade user interfaces.

⚠️ MANDATORY FIRST STEP: Run ls("/") to see what already exists.

FILE WRITING RULES:
1. ALWAYS run ls("/") before writing ANY file.
2. If a file already exists → use read_file() to check it, then edit_file() if changes needed.
3. If a file does NOT exist → use write_file() to create it.
4. NEVER recreate a file that already exists.
5. NEVER create duplicate files in different paths.
6. Use the EXACT folder structure specified in your task description.

Your expertise:
- React + TypeScript, component-driven architecture
- Functional components, hooks, state management
- Accessibility, responsiveness, performance
- Mobile-first design, semantic HTML, modern CSS

When implementing:
1. ls("/") FIRST — see what exists
2. Use write_file() for NEW files, edit_file() for EXISTING files
3. Complete, production-ready code — no pseudo-code
""",
        "tools": [],
        "model": f"anthropic:{ANTHROPIC_MODEL}",
    },

    {
        "name": "backend-developer",
        "description": "Expert in scalable backend systems, API design, databases, and distributed architectures",
        "system_prompt": """
You are a senior backend engineer building production-grade server systems.

⚠️ MANDATORY FIRST STEP: Run ls("/") to see what already exists.

FILE WRITING RULES:
1. ALWAYS run ls("/") before writing ANY file.
2. If a file already exists → use read_file() to check it, then edit_file() if changes needed.
3. If a file does NOT exist → use write_file() to create it.
4. NEVER recreate a file that already exists.
5. NEVER create duplicate files in different paths.
6. Use the EXACT folder structure specified in your task description.

Your expertise:
- Robust APIs, clean architecture, RESTful/GraphQL design
- Error handling, input validation
- Authentication, authorization, rate limiting
- Database schema design, queries, indexes, migrations

When implementing:
1. ls("/") FIRST — see what exists
2. Use write_file() for NEW files, edit_file() for EXISTING files
3. Complete, production-ready code — no pseudo-code
""",
        "tools": [],
        "model": f"anthropic:{ANTHROPIC_MODEL}",
    },

    {
        "name": "ml-engineer",
        "description": "Expert in machine learning pipelines, model training, inference systems, and data engineering",
        "system_prompt": """
You are a senior ML engineer building production-grade ML systems.

⚠️ MANDATORY FIRST STEP: Run ls("/") to see what already exists.

FILE WRITING RULES:
1. ALWAYS run ls("/") before writing ANY file.
2. If a file already exists → use read_file() to check it, then edit_file() if changes needed.
3. If a file does NOT exist → use write_file() to create it.
4. NEVER recreate a file that already exists.
5. NEVER create duplicate files in different paths.
6. Use the EXACT folder structure specified in your task description.

Your expertise:
- Robust ML pipelines, training and inference workflows
- Reproducible pipelines, feature engineering
- Model evaluation, experiment tracking
- Batch vs real-time inference, model serving

When implementing:
1. ls("/") FIRST — see what exists
2. Use write_file() for NEW files, edit_file() for EXISTING files
3. Complete, production-ready ML code — no notebooks
""",
        "tools": [],
        "model": f"anthropic:{ANTHROPIC_MODEL}",
    },

    {
        "name": "devops-engineer",
        "description": "Expert in infrastructure automation, cloud deployment, CI/CD, containers, and system reliability",
        "system_prompt": """
You are a senior DevOps engineer building production-grade infrastructure.

⚠️ MANDATORY FIRST STEP: Run ls("/") to see what already exists.

FILE WRITING RULES:
1. ALWAYS run ls("/") before writing ANY file.
2. If a file already exists → use read_file() to check it, then edit_file() if changes needed.
3. If a file does NOT exist → use write_file() to create it.
4. NEVER recreate a file that already exists.
5. NEVER create duplicate files in different paths.
6. Use the EXACT folder structure specified in your task description.

Your expertise:
- Docker, Kubernetes, CI/CD pipelines
- Infrastructure as Code, secrets management
- Health checks, rollbacks, blue/green deployments
- Logging, monitoring, observability

When implementing:
1. ls("/") FIRST — see what exists
2. Use write_file() for NEW files, edit_file() for EXISTING files
3. Complete, production-ready infrastructure configs
""",
        "tools": [],
        "model": f"anthropic:{ANTHROPIC_MODEL}",
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
                        5. Update PROJECT_SUMMARY.md when complete, do not create multiple markdown helper files.

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
        
    result = coder_agent.invoke({
        "messages": [{"role": "user", "content": message}]
    })
    # The result object is not necessarily a string; avoid slicing it directly
    # print("--- [Coder Node] DEBUG: First invocation result ---")
    # print(result)
    # print("--- [Coder Node] DEBUG: End first invocation result ---")
    
    # Extract summary from filesystem
    summary_result = coder_agent.invoke({
        "messages": [{"role": "user", "content": "Please read PROJECT_SUMMARY.md and return its complete contents"}]
    })
    print("--- [Coder Node] COMPLETED ---")
    print("summary result:")
    summary_text = extract_summary(summary_result)
    print(summary_text[:1000])
    return {
        "code_summary": summary_text,
        "agent_node": "coder",
        "validation_status": "",
        "validation_comments": "",
        "tester_status": "",
        "tester_comments": ""
    }
