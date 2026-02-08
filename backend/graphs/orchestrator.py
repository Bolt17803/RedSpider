from typing import TypedDict, Annotated, List
import os
import operator
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from deepagents import create_deep_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from prompts.architect import architect_backstory
from prompts.planner import planner_backstory
from prompts.coder import coder_backstory
from prompts.validation import validation_backstory
from prompts.tester import tester_backstory
from tools.tester import execute_command
from pathlib import Path
from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt
from nodes.coder import specialized_subagents, coder_node
from nodes.validation import validation_node, should_continue_coding
from nodes.tester import tester_node, should_continue_testing
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import TodoListMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.subagents import SubAgentMiddleware
from typing import Any
from functools import partial

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")
coder_agent: Any = None
validation_agent: Any = None
tester_agent: Any = None

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

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,  # Using 1.5-flash for better rate limits
    temperature=0.2,
    max_retries=2,
)

deepagent_llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,  # Using 1.5-flash for better rate limits
    temperature=0.4,
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
    response_format=ArchitectOutput
)

def architect_node(state: GraphState):  # <-- Remove 'checkpointer'
    '''
    this node will pass user response to the agent
    '''
    print("--- [Architect Node] STARTED ---")
    user_response = state.get('user_response')

    # === REMOVE ALL MANUAL LOADING ===
    # Get messages directly from state. Default to empty list if it's the first run.
    messages = list(state.get('architect_messages', [])) # Create a copy!

    # Add the new user message
    messages.append(HumanMessage(content=user_response))

    response = architect_agent.invoke(
        {
            "messages": messages
        }
    )
    # Get the full, updated history from the agent's response
    full_history = response['messages'] 
    
    # Calculate delta: only return the new messages (User + AI)
    # The 'messages' list we passed in had the new user message appended.
    # The 'full_history' has that + AI response.
    # We want to return the User msg + AI msg to be appended to the global state.
    # But wait, 'state.get' gave us existing history.
    # So we want full_history - existing_history.
    
    existing_len = len(state.get('architect_messages', []))
    new_messages = full_history[existing_len:] 
    # architect_response = response['messages'][-1].content
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
    print("--- [Architect Node] COMPLETED ---")
    # print(f"Architect response: {architect_response}")
    return {
        'architect_response': architect_response,
        'architect_messages': new_messages,  # <-- This saves the memory
        'agent_node': 'architect'
    }

def architect_response_review_node(state: GraphState):
    # (This function is fine, no changes needed)
    print("--- [Architect REVIEW NODE] STARTED ---")
    output_to_review = state["architect_response"]
    feedback = interrupt({
        "instruction": "Please respond to the agent... Type 'approve' if you want to proceed with the currently obtained goals, else mention your changes.",
        "content_to_review": output_to_review
    })
    print("--- [Architect REVIEW NODE] COMPLETED ---")
    return {'user_response': feedback}

def architect_decision_node(state: GraphState):
    # (This function is fine, no changes needed)
    if state['user_response'].lower() == "approve":
        workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])
        architect_response_file_path= os.path.join(workspace_path, "architect_response.txt")
        with open(architect_response_file_path, "w", encoding="utf-8") as f:
            f.write(state["architect_response"])
        return END
    else:
        return "agent"
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
    print("--- [Planner Node] STARTED ---")
    messages = list(state.get('planner_messages', [])) # Create a copy!

    # Add the new user message
    if state["agent_node"] == 'architect':
        l=state["architect_response"].split("##")
        input_msg = "Higher Level Objectives: \n\n"
        input_msg+= l[1]
        input_msg += "\n\n the above are the user goals to be achieved, generate an end-to end plan to make the goals to reality."
        messages = [HumanMessage(content=input_msg)]
    else:
        input_msg = state["user_response"]
        messages.append(HumanMessage(content=input_msg))
    
    response = planner_agent.invoke(
        {
            "messages": messages
        },
        config={"tags": ["planner_stream"]}
    )
    print("--- [Planner Node] COMPLETED ---")
    # === REMOVE ALL MANUAL SAVING ===
    full_history = response['messages']
    planner_response = response['messages'][-1].content
    
    existing_len = len(state.get('planner_messages', []))
    new_messages = full_history[existing_len:]
    
    # Return the new state. The checkpointer will automatically save this.
    return {
        'planner_response': planner_response,
        'planner_messages': new_messages,  # <-- This saves the memory
        'agent_node': 'planner'
    }

def planner_response_review_node(state: GraphState):
    # (This function is fine, no changes needed)
    print("--- [Planner REVIEW NODE] STARTED ---")
    output_to_review = state["planner_response"]
    feedback = interrupt({
        "instruction": "Please respond to the agent... Type 'approve' if you want to proceed, else mention your changes.",
        "content_to_review": output_to_review
    })
    print("--- [Planner REVIEW NODE] COMPLETED ---")
    return {'user_response': feedback}

def planner_decision_node(state: GraphState):
    # (This function is fine, no changes needed)
    if state['user_response'].lower() == "approve":
        print("--- [Planner Decision Node : ENDING] ---")
        workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])
        planner_response_file_path= os.path.join(workspace_path, "planner_response.txt")
        with open(planner_response_file_path, "w", encoding="utf-8") as f:
            f.write(state["planner_response"])
        return END
    else:
        print("--- [Planner Decision Node : LOOPING] ---")
        return "agent"

#----------------------------------------------------------------CODER, VALIDATION, TESTER DEEPAGENTs----------------------------------------------------    
def create_coder_agent(path: str):
    global coder_agent
    root_dir = Path(path).resolve().as_posix()  # Ensure absolute path in POSIX format
    backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    coder_agent = create_deep_agent(
            model=deepagent_llm,
            system_prompt=coder_backstory(),#"you are an awesome coder, you have access to write, read tools, use them correctly for the task",#coder_backstory(),
            backend=backend,
        )
        # subagents=specialized_subagents

def create_validation_agent(path: str):
    global validation_agent
    root_dir = Path(path).resolve().as_posix()  # Ensure absolute path in POSIX format
    backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    validation_agent = create_deep_agent(
            model=deepagent_llm,
            system_prompt=validation_backstory(),
            backend=backend
        )

def create_tester_agent(path: str):
    global tester_agent
    root_dir = Path(path).resolve().as_posix()  # Ensure absolute path in POSIX format
    backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    tester_agent = create_deep_agent(
            model=deepagent_llm,
            system_prompt=tester_backstory(),
            tools = [execute_command],
            backend=backend
        )

#----------------------------------------------------------------HUMAN RESPONSE NODE----------------------------------------------------
def human_response_node(state: GraphState):
    # (This function is fine, no changes needed)
    print("--- [Human Response REVIEW NODE] STARTED ---")
    output_to_review = state["code_summary"]
    feedback = interrupt({
        "instruction": "Please respond to the agent... Type 'approve' if you want to proceed, else mention your changes.",
        "content_to_review": output_to_review
    })
    print("--- [Human Response REVIEW NODE] COMPLETED ---")
    return {
        'user_response': feedback,
        'agent_node': 'human_response'
        }

def review_human_response(state: GraphState):
    if state['user_response'].lower() == "approve":
        print("--- [Review Human Response Node : ENDING] ---")
        return END
    else:
        print("--- [Review Human Response Node : LOOPING] ---")
        return "code"

#----------------------------------------------------------------DEEPAGENT INITIALIZATION----------------------------------------------------
def init_deepagents(state: GraphState):
    workspace_path = os.path.join(PLAYGROUND_PATH, state["title"])
    os.makedirs(workspace_path, exist_ok=True)
    create_coder_agent(workspace_path)
    create_validation_agent(workspace_path)
    create_tester_agent(workspace_path)
#----------------------------------------------------------------GRAPH INVOKER----------------------------------------------------

def graph_invoker(checkpointer=None):
    '''
    this module will invoke the entire graph network
    '''
    builder = StateGraph(GraphState)
    if not checkpointer:
        checkpointer = MemorySaver()

    builder.add_node("init_deepagents", init_deepagents)
    builder.add_node("architect_agent", architect_node)
    builder.add_node("architect_review", architect_response_review_node)
    builder.add_node("planner_agent", planner_node)
    builder.add_node("planner_review", planner_response_review_node)
    builder.add_node("coder_agent", lambda state: coder_node(state, coder_agent))
    builder.add_node("validation_agent", lambda state: validation_node(state, validation_agent))
    builder.add_node("tester_agent", lambda state: tester_node(state, tester_agent))
    builder.add_node("human_response", human_response_node)

    builder.set_entry_point("init_deepagents")
    builder.add_edge("init_deepagents", "architect_agent")
    builder.add_edge("architect_agent", "architect_review")
    builder.add_edge("planner_agent", "planner_review")
    builder.add_edge("coder_agent", "validation_agent")
    
    builder.add_conditional_edges(
        "architect_review",
        architect_decision_node,
        {
            END: "planner_agent",
            "agent": "architect_agent"
        }

    )
    builder.add_conditional_edges(
        "planner_review",
        planner_decision_node,
        {
            END: "coder_agent",
            "agent": "planner_agent"
        }
    )
    
    builder.add_conditional_edges(
        "validation_agent",
        should_continue_coding,
        {
            "code": "coder_agent",
            "test": "tester_agent"
        }
    )
    builder.add_conditional_edges(
        "tester_agent",
        should_continue_testing,
        {
            "human_response": "human_response",
            "code": "coder_agent"
        }
    )
    builder.add_conditional_edges(
        "human_response",
        review_human_response,
        {
            END: END,
            "code": "coder_agent"
        }
    )

    graph = builder.compile(checkpointer=checkpointer)
    return graph
