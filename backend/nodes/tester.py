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

def should_continue_testing(state: GraphState) -> str:
    """Router after testing"""
    if state["tester_status"] == "TESTS_PASSED":
        return "human_response"
    else:
        return "code"

def extract_test_result(result) -> dict:
    """
    Extract test status and comments.
    Returns: {"status": "TESTS_PASSED/FAILED", "comments": "..."}
    """
    if hasattr(result, 'messages'):
        content = result.messages[-1].content
    else:
        content = str(result)
    
    content_lower = content.lower()
    status = "TESTS_PASSED" if "tests_passed" in content_lower else "TESTS_FAILED"
    
    return {"status": status, "comments": content.strip()}

def tester_node(state: GraphState, tester_agent: Any):
    """Execute testing agent"""
    print("--- [Tester Node] STARTED ---")
    result = tester_agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
Test this implementation and provide detailed feedback for the coding agent.

CODE SUMMARY:
{state['code_summary']}

YOUR TESTING PROCESS:
1. Read PROJECT_SUMMARY.md to understand:
   - What should be tested
   - Setup requirements
   - Environment variables needed
   - Execution commands

2. Ask the user to provide any required environment variables

3. Execute setup steps (install dependencies, etc.)

4. Run the code/tests and capture all output

5. Analyze the results

REQUIRED OUTPUT FORMAT:
================================
TEST EXECUTION REPORT
================================

SETUP:
[What setup steps were performed]

EXECUTION:
[What commands were run]

RESULTS:
[Detailed output from execution]

ERRORS (if any):
[List each error with:
 - Error message
 - Stack trace
 - Likely cause
 - Suggested fix
 - Which file(s) need modification
]

GUIDANCE FOR CODING AGENT:
[If tests failed, provide specific instructions on:
 - What needs to be fixed
 - In which files
 - Suggested approach to fix
]

================================
Final Status: TESTS_PASSED or TESTS_FAILED
================================

If TESTS_FAILED, the error details and guidance will be used by the coding agent to create todo tasks for fixes.
"""
        }]
    })
    
    test_result = extract_test_result(result)
    print("--- [Tester Node] COMPLETED ---")
    print("test result:")
    print(test_result["comments"][:3000])
    return {
        "tester_status": test_result["status"],
        "tester_comments": test_result["comments"],
        "agent_node": "tester"
    }
