from typing import TypedDict, Annotated, List
import os
import operator
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts.architect import architect_backstory
from pydantic import BaseModel, Field
from prompts.planner import planner_backstory
from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

class GraphState(TypedDict):
    '''
    this is the state dictionary containing the inital user query, architect response
    and the planner response
    '''
    agent_node: str
    user_response: str
    architect_response: str
    planner_response: str
    final_architect_response: str
    final_planner_response: str
    architect_messages: Annotated[list, operator.add]
    planner_messages: Annotated[list, operator.add]

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", # Using 1.5-flash as 2.5 is not yet public
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)
#------------------------------------------------------------------ARCHITECT AGENT------------------------------------------------
class ArchitectOutput(BaseModel):
    """Structured output for the architect agent."""
    project_goals: List[str] = Field(
        description="A list of clear, rigid project goals derived from the user's request."
    )
    follow_up_questions: List[str] = Field(
        description="A list of questions to ask the user to clarify any ambiguities or gather more information."
    )

architect_agent = create_agent(
    model=llm,
    system_prompt=architect_backstory(),
    tools=[],
    response_format= ArchitectOutput
)

def architect_node(state: GraphState):  # <-- Remove 'checkpointer'
    '''
    this node will pass user response to the agent
    '''
    user_response = state['user_response']

    # === REMOVE ALL MANUAL LOADING ===
    # Get messages directly from state. Default to empty list if it's the first run.
    messages = state.get('architect_messages', [])

    # Add the new user message
    messages.append(HumanMessage(content=user_response))

    response = architect_agent.invoke(
        {
            "messages": messages
        }
    )

    # Get the full, updated history from the agent's response
    new_messages = response['messages']
    print('-------------------------')
    print(new_messages)
    
    structured_output: ArchitectOutput = response.get('structured_response')

    if structured_output:
        # (Your existing formatting logic is fine)
        formatted_response = "## Project Goals\n"
        if structured_output.project_goals:
            for i, goal in enumerate(structured_output.project_goals, 1):
                formatted_response += f"{i}. {goal}\n"
        else:
            formatted_response += "project goals are not properly defined. Answer the below follow-up questions\n"
        
        formatted_response += "\n## Follow-up Questions\n"
        if structured_output.follow_up_questions:
            for i, question in enumerate(structured_output.follow_up_questions, 1):
                formatted_response += f"{i}. {question}\n"
        else:
            formatted_response += "No follow-up questions.\n"
        
        architect_response = formatted_response
    else:
        architect_response = response['messages'][-1].content
    
    # Return the new state. The checkpointer will automatically save this.
    print("--- [Architect Node] DEBUG: Returning new state. ---")
    return {
        'architect_response': architect_response,
        'architect_messages': new_messages,  # <-- This saves the memory
        'agent_node': 'architect'
    }

def architect_response_review_node(state: GraphState):
    # (This function is fine, no changes needed)
    output_to_review = state["architect_response"]
    feedback = interrupt({
        "instruction": "Please respond to the agent... Type 'approve' if you want to proceed with the currently obtained goals, else mention your changes.",
        "content_to_review": output_to_review
    })
    print("--- [Architect REVIEW NODE] DEBUG: Returning new state. ---")
    return {'user_response': feedback}

# def decision_node(state: GraphState):
#     # (This function is fine, no changes needed)
#     if state['user_response'].lower() == "approve":
#         return END
#     else:
#         return "agent"
#----------------------------------------------------------------PLANNER AGENT----------------------------------------------------
planner_agent = create_agent(
    model=llm,
    system_prompt=planner_backstory(),
    tools=[]
)

def planner_node(state: GraphState):  # <-- Remove 'checkpointer'
    '''
    this node will pass user response to the agent, using conversational memory from state
    '''
    # === REMOVE ALL MANUAL LOADING ===
    # Get messages directly from state.
    messages = state.get('planner_messages', [])

    # Add the new user message
    if state["agent_node"] == 'architect':
        print("first input to the planner agent")
        input_msg = "Higher Level Objectives: \n\n" + state["architect_response"]
        input_msg += "\n\n the above are the user goals to be achieved, generate an end-to end plan to make the goals ton reality."
        # Start a new history for the planner
        messages = [HumanMessage(content=input_msg)]
    else:
        print("including user response for modifications")
        input_msg = state["user_response"]
        messages.append(HumanMessage(content=input_msg))
    print("\n--- [Planner Node] DEBUG: Invoking agent... ---")
    response = planner_agent.invoke(
        {
            "messages": messages
        }
    )
    print("--- [Planner Node] DEBUG: Agent invocation complete. ---") # <-- ADD THIS
    # === REMOVE ALL MANUAL SAVING ===
    new_messages = response['messages']
    planner_response = response['messages'][-1].content
    
    # Return the new state. The checkpointer will automatically save this.
    return {
        'planner_response': planner_response,
        'planner_messages': new_messages,  # <-- This saves the memory
        'agent_node': 'planner'
    }

def planner_response_review_node(state: GraphState):
    # (This function is fine, no changes needed)
    output_to_review = state["planner_response"]
    feedback = interrupt({
        "instruction": "Please respond to the agent... Type 'approve' if you want to proceed, else mention your changes.",
        "content_to_review": output_to_review
    })
    print("--- [Planner REVIEW NODE] DEBUG: Returning new state. ---")
    return {'user_response': feedback}

def decision_node(state: GraphState):
    # (This function is fine, no changes needed)
    if state['user_response'].lower() == "approve":
        print("--- [Decision Node] DEBUG: ENDING. ---")
        return END
    else:
        print("--- [Decision Node] DEBUG: LOOPING. ---")
        return "agent"
    
#----------------------------------------------------------------GRAPH INVOKER----------------------------------------------------
def graph_invoker():
    '''
    this module will invoke the entire graph network
    '''
    builder = StateGraph(GraphState)
    checkpointer = MemorySaver()

    builder.add_node("architect_agent", architect_node)
    builder.add_node("architect_review", architect_response_review_node)
    builder.add_node("planner_agent", planner_node)
    builder.add_node("planner_review", planner_response_review_node)

    builder.set_entry_point("architect_agent")
    builder.add_edge("architect_agent", "architect_review")
    builder.add_conditional_edges(
        "architect_review",
        decision_node,
        {
            END: "planner_agent",
            "agent": "architect_agent"
        }

    )
    builder.add_conditional_edges(
        "planner_review",
        decision_node,
        {
            END: END,
            "agent": "planner_agent"
        }

    )

    graph = builder.compile(checkpointer=checkpointer)
    return graph
