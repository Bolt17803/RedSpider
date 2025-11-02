import os
import uuid
from typing import TypedDict
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import MemorySaver
from nodes.architect import create_architect_agent_graph
from nodes.planner import create_planner_agent_graph

load_dotenv()
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
# Set environment variables in Python instead of using shell 'export' statements
os.environ["LANGSMITH_TRACING"] = os.environ.get("LANGSMITH_TRACING", "true")
os.environ["LANGSMITH_ENDPOINT"] = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
# Do not hardcode secret API keys in source; prefer .env or external config
if LANGSMITH_API_KEY:
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
# Optionally set project from environment or default
os.environ["LANGSMITH_PROJECT"] = os.environ.get("LANGSMITH_PROJECT", "pr-excellent-medal-68")

class GraphState(TypedDict):
    '''
    this is the state dictionary containing the inital user query, architect response
    and the planner response
    '''
    initial_query: str
    final_architect_response: str
    final_planner_response: str

def run_architect_node(state: GraphState, checkpointer, thread_id):
    '''
    this node runs the architect sub graph network for obtaining clear set of goals
    '''

    config = {"configurable": {"thread_id": thread_id}}

    init_user_query = state["initial_query"]
    
    # === INITIALIZE MESSAGES ===
    architect_initial_state = {
        "user_response": init_user_query, 
        "thread_id": 'architectworkflow',
        "messages": []  # <-- Initialize the memory
    }

    architect_graph = create_architect_agent_graph(checkpointer=checkpointer)
    print("Invoking architect graph...")
    # (rest of the function is fine)
    architect_current_state = architect_graph.invoke(architect_initial_state, config)

    while "__interrupt__" in architect_current_state:
        interrupt_data = architect_current_state["__interrupt__"]
        interrupt_value = interrupt_data[0].value
        print("\n--- ❗ ARCHITECT REVIEW (from Super-Graph) ---")
        print(f"Instruction: {interrupt_value['instruction']}")
        print("---------------------------------")
        print(f"Agent's Output:\n{interrupt_value['content_to_review']}")
        print("---------------------------------")

        user_feedback = input("Your feedback on the *goals* ('approve' to continue): ")
        print("\n====================================")

        architect_current_state = architect_graph.invoke(
            Command(resume=user_feedback),
            config,
        )

    architect_response = architect_current_state["architect_response"]
    return {"final_architect_response": architect_response}

def run_planner_node(state: GraphState, checkpointer, thread_id):
    '''
    this node runs the planner sub graph network for obtaining clear set of execution steps for completing the user goals.
    '''

    config = {"configurable": {"thread_id": thread_id}}

    final_architect_response = state["final_architect_response"]
    
    # === INITIALIZE MESSAGES ===
    planner_initial_state = {
        "architect_response": final_architect_response, 
        "user_response": None, 
        "thread_id": 'plannerworkflow',
        "messages": []  # <-- Initialize the memory
    }

    planner_graph = create_planner_agent_graph(checkpointer=checkpointer)
    print("Invoking planner agent graph...")
    # (rest of the function is fine)
    planner_current_state = planner_graph.invoke(planner_initial_state, config)

    while "__interrupt__" in planner_current_state:
        interrupt_data = planner_current_state["__interrupt__"]
        interrupt_value = interrupt_data[0].value

        print("\n--- ❗ PLANNER REVIEW (from Super-Graph) ---")
        print(f"Instruction: {interrupt_value['instruction']}")
        print("---------------------------------")
        print(f"Agent's Plan:\n{interrupt_value['content_to_review']}")
        print("---------------------------------")

        user_feedback = input("Your feedback on the *plan* ('approve' to continue): ")
        print("\n====================================")

        planner_current_state = planner_graph.invoke(
            Command(resume=user_feedback),
            config,
        )

    planner_response = planner_current_state["planner_response"]
    return {"final_planner_response": planner_response}

def invoke_workflow():
    '''
    this will invoke the entire graph workflow
    '''
    builder = StateGraph(GraphState)
    checkpointer = MemorySaver()
    
    thread_id = "main-workflow"
    builder.add_node("architect", lambda state: run_architect_node(state, checkpointer, thread_id))
    builder.add_node("planner", lambda state: run_planner_node(state, checkpointer, thread_id))

    builder.set_entry_point("architect")
    builder.add_edge("architect", "planner")
    builder.add_edge("planner", END)

    builder_graph = builder.compile(checkpointer=checkpointer)

    initial_query = input("Enter a task you want to accomplish related in ai dev, data engineering or full stack dev: \n")
    config = {"configurable": {"thread_id": "main-workflow"}}
    final_state = builder_graph.invoke(
        {"initial_query": initial_query},
        config
    )

    print("\n--- ✅ Entire Workflow Finished ---")
    print("\nFinal Architect Goals:")
    print(final_state['final_architect_response'])
    print("\nFinal Planner Response:")
    print(final_state['final_planner_response'])

if __name__ == "__main__":
    invoke_workflow()