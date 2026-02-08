from typing import Any, Annotated, List, TypedDict
import operator

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

def should_continue_coding(state: GraphState) -> str:
    """Router after validation"""
    if "COMPLETE" in state["validation_status"]:
        return "test"
    else:
        return "code"

def extract_validation_result(result) -> dict:
    """
    Extract validation status and comments.
    Returns: {"status": "VALIDATION_COMPLETE/INCOMPLETE", "comments": "..."}
    """
    if hasattr(result, 'messages'):
        content = result.messages[-1].content
    else:
        content = str(result)
    
    content_lower = content.lower()
    status = "VALIDATION_COMPLETE" if "validation_complete" in content_lower else "VALIDATION_INCOMPLETE"
    
    return {"status": status, "comments": content.strip()}

def validation_node(state: GraphState, validation_agent: Any):
    """Execute validation agent with file access"""
    print("--- [Validation Node] STARTED ---")
    result = validation_agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
You are validating a code implementation against the original plan.

ORIGINAL PLAN:
{state['planner_response']}

CODE SUMMARY FROM CODING AGENT:
{state['code_summary']}

YOUR VALIDATION PROCESS:
1. First, use ls() to see the complete project structure
2. For EACH feature mentioned in the plan:
   a. Check if it's mentioned in the code summary
   b. Use read_file() to examine the actual implementation files
   c. Verify the code actually implements the requirements
3. Create a detailed report with:
   - ✅ Features that are fully implemented (with file references)
   - ❌ Features that are missing or incomplete (with specific gaps)

Be thorough - READ THE ACTUAL CODE, don't just trust the summary!

REQUIRED OUTPUT FORMAT:
================================
VALIDATION REPORT
================================

✅ COMPLETED FEATURES:
[List each completed feature with:
 - Feature name
 - File location
 - Specific requirements met
]

❌ MISSING/INCOMPLETE FEATURES:
[For each incomplete feature, provide:
 - Feature name
 - What is missing (be specific)
 - What needs to be implemented
 - Which files need to be created/modified
]

================================
Final Status: VALIDATION_COMPLETE or VALIDATION_INCOMPLETE
================================

If VALIDATION_INCOMPLETE, the "MISSING/INCOMPLETE FEATURES" section will be used by the coding agent to create todo tasks.
"""
        }]
    })
    
    # The validation agent will use its filesystem tools:
    # - ls() to see all files
    # - read_file() to examine implementations
    # It has access to the same ./generated_project directory
    
    validation_result = extract_validation_result(result)
    print("--- [Validation Node] COMPLETED ---")
    print("validation result:")
    print(validation_result["comments"][:3000])
    return {
        "validation_status": validation_result["status"],
        "validation_comments": validation_result["comments"],
        "agent_node": "validation"
    }
