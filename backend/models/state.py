from typing import Annotated, List, Optional, TypedDict
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
    # Validation HITL state fields
    validation_pending_command: Optional[str]
    validation_user_decision: Optional[str]
    # Summarizer output
    final_summary: str
    errors: List[str]
