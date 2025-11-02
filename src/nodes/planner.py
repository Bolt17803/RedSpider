import os
from typing import TypedDict, List  # <-- Import List
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, BaseMessage  # <-- Import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_google_genai import ChatGoogleGenerativeAI

from prompts.planner import planner_backstory
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", # Using 1.5-flash as 2.5 is not yet public
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

class SubGraphState(TypedDict):
    '''
    this is the state dictionary for the planner agent, whose job is to plan the entire steps
    to achieve the user task goals
    '''
    planner_response: str
    architect_response: str
    user_response: str
    thread_id: str
    messages: List[BaseMessage]  # <-- ADD THIS. This is your memory.

planner_agent = create_agent(
    model=llm,
    system_prompt=planner_backstory(),
    tools=[]
)

def planner_node(state: SubGraphState):  # <-- Remove 'checkpointer'
    '''
    this node will pass user response to the agent, using conversational memory from state
    '''
    thread_id = state['thread_id']
    config = {"configurable": {"thread_id": thread_id}}

    # === REMOVE ALL MANUAL LOADING ===
    # Get messages directly from state.
    messages = state.get('messages', [])

    # Add the new user message
    if state["user_response"] is None:
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
        },
        config
    )
    print("--- [Planner Node] DEBUG: Agent invocation complete. ---") # <-- ADD THIS
    # === REMOVE ALL MANUAL SAVING ===
    new_messages = response['messages']
    planner_response = response['messages'][-1].content
    
    # Return the new state. The checkpointer will automatically save this.
    return {
        'planner_response': planner_response,
        'messages': new_messages  # <-- This saves the memory
    }

def planner_response_review_node(state: SubGraphState):
    # (This function is fine, no changes needed)
    output_to_review = state["planner_response"]
    feedback = interrupt({
        "instruction": "Please respond to the agent... Type 'approve' if you want to proceed, else mention your changes.",
        "content_to_review": output_to_review
    })
    return {'user_response': feedback}

def decision_node(state: SubGraphState):
    # (This function is fine, no changes needed)
    if state['user_response'].lower() == "approve":
        return END
    else:
        return "agent"

def create_planner_agent_graph(checkpointer):
    '''
    this will return the planner agent that will interact with the user to get rigid goals.
    '''
    planner_builder = StateGraph(SubGraphState)

    # === REMOVE THE LAMBDA ===
    planner_builder.add_node("agent", planner_node)
    
    planner_builder.add_node("review", planner_response_review_node)
    planner_builder.set_entry_point("agent")
    planner_builder.add_edge("agent", "review")
    planner_builder.add_conditional_edges(
        "review",
        decision_node,
        {
            END: END,
            "agent": "agent"
        }
    )

    planner_graph = planner_builder.compile(checkpointer=checkpointer)

    return planner_graph