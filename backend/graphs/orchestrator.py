from typing import Any, List
import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field
from typing import Literal
from prompts.architect import architect_backstory
from prompts.planner import planner_backstory_short_v2
from prompts.coder import coder_backstory
from prompts.validation import validation_backstory
from prompts.summarizer import summarizer_backstory
from tools.validation import execute_command
from pathlib import Path
from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt
from nodes.coder import specialized_subagents, coder_node
from nodes.validation import validation_node, validation_approval_node, should_continue_coding, should_continue_after_validation_approval, validation_subagents
from nodes.summarizer import summarizer_node
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import TodoListMiddleware, HumanInTheLoopMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.subagents import SubAgentMiddleware
from models.state import GraphState
from functools import partial
from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL")
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
coder_agent: Any = None
validation_agent: Any = None
tester_agent: Any = None



llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # Using 1.5-flash for better rate limits
    temperature=0.2,
    max_retries=2,
)
# llm = ChatOllama(
#     model="qwen2.5-coder:3b",
#     temperature=0.2,
#     max_retries=2,
#     think=False
# )
# llm = ChatGroq(
#     model_name="meta-llama/llama-prompt-guard-2-86m",
#     temperature=0.2
# )
# llm = ChatOpenAI(
#     api_key=OPENROUTER_API_KEY,
#     base_url="https://openrouter.ai/api/v1",
#     model="meta-llama/llama-3.3-70b-instruct",
# )

# build a to-do list app; features to be task-creaation, editing, deleating, marking as complete ; user will be individual, use local_storage for data persistence, use type script nodejs for frontend, keep the design to attract the children from age 9-15 yrs; I do not need deployment code, just the main code

# deepagent_llm = ChatGoogleGenerativeAI(
#     model="gemini-2.5-pro",  # Using 1.5-flash for better rate limits
#     temperature=0.2,
#     max_retries=2,
# )
deepagent_llm = ChatAnthropic(
    model=ANTHROPIC_MODEL,
    temperature=0.3,
)
# deepagent_llm = ChatOllama(
#     model="qwen2.5-coder:3b",
#     temperature=0.3,
#     think=False
# )
# deepagent_llm = ChatGroq(
#     model_name="meta-llama/llama-prompt-guard-2-86m",
#     temperature=0.3
# )
# deepagent_llm = init_chat_model(
#     model="qwen/qwen3-coder",  # Specify the Qwen model
#     model_provider="openai",
#     base_url="https://openrouter.ai/api/v1",    
#     api_key=OPENROUTER_API_KEY
# )
# deepagent_llm = ChatOpenAI(
#     api_key=OPENROUTER_API_KEY,
#     base_url="https://openrouter.ai/api/v1",
#     model="meta-llama/llama-3.3-70b-instruct",
# )


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
    system_prompt=planner_backstory_short_v2(),
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
    root_dir = str(Path(path).resolve())
    backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    coder_agent = create_deep_agent(
            model=deepagent_llm,
            system_prompt=coder_backstory(),#"you are an awesome coder, you have access to write, read tools, use them correctly for the task",#coder_backstory(),
            backend=backend,
            subagents=specialized_subagents
        )

class ValidationResult(BaseModel):
    """Structured output from the tester agent."""
    test_status: Literal["VALIDATION_COMPLETE", "VALIDATION_INCOMPLETE"] = Field(
        description="Overall validation status: VALIDATION_COMPLETE if all validation tests are passed, VALIDATION_INCOMPLETE if any validation test fails"
    )
    comments: str = Field(
        description="Detailed validation results, error descriptions, or command output summary"
    )

def create_validation_agent(path: str):
    global validation_agent
    root_dir = str(Path(path).resolve())
    backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    validation_agent = create_deep_agent(
            model=deepagent_llm,
            system_prompt=validation_backstory(),
            backend=backend,
            checkpointer=MemorySaver(),
            subagents=validation_subagents,
            tools=[execute_command],
            middleware=[
                HumanInTheLoopMiddleware(
                    interrupt_on={
                        "execute_command": True,
                    },
                    description_prefix="Approve this command execution:"
                )
            ]
        )


def create_summarizer_agent(path: str):
    global summarizer_agent
    root_dir = str(Path(path).resolve())
    backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    summarizer_agent = create_deep_agent(
            model=deepagent_llm,
            system_prompt=summarizer_backstory(),
            backend=backend,
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
    create_summarizer_agent(workspace_path)
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
    async def _validation_agent_node(state, config):
        return await validation_node(state, validation_agent, config)
    builder.add_node("validation_agent", _validation_agent_node)
    builder.add_node("validation_approval", validation_approval_node)
    builder.add_node("summarizer_agent", lambda state: summarizer_node(state, summarizer_agent))
    builder.add_node("human_response", human_response_node)

    builder.set_entry_point("init_deepagents")
    builder.add_edge("init_deepagents", "architect_agent")
    builder.add_edge("architect_agent", "architect_review")
    builder.add_edge("planner_agent", "planner_review")
    builder.add_edge("coder_agent", "validation_agent")
    builder.add_edge("summarizer_agent", "human_response")
    
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
            "summarize": "summarizer_agent",
            "validation_approval": "validation_approval"
        }
    )
    builder.add_conditional_edges(
        "validation_approval",
        should_continue_after_validation_approval,
        {
            "validation": "validation_agent"
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
