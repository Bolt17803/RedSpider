import os
from typing import TypedDict, List  # <-- Import List
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, BaseMessage  # <-- Import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import List

from prompts.architect import architect_backstory
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
    this is the state dictionary for the architect agent, whose job is to get rigid goals from the
    user and help further agents to easily accomplish the task and increase user satisfaction.
    '''
    architect_response: str
    user_response: str
    thread_id: str
    messages: List[BaseMessage]  # <-- ADD THIS. This is your memory.

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

def architect_node(state: SubGraphState):  # <-- Remove 'checkpointer'
    '''
    this node will pass user response to the agent
    '''
    user_response = state['user_response']
    thread_id = state['thread_id']
    config = {"configurable": {"thread_id": thread_id}}

    # === REMOVE ALL MANUAL LOADING ===
    # Get messages directly from state. Default to empty list if it's the first run.
    messages = state.get('messages', [])

    # Add the new user message
    messages.append(HumanMessage(content=user_response))

    response = architect_agent.invoke(
        {
            "messages": messages
        },
        config
    )

    # === REMOVE ALL MANUAL SAVING ===
    # Get the full, updated history from the agent's response
    new_messages = response['messages']

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
    return {
        'architect_response': architect_response,
        'messages': new_messages  # <-- This saves the memory
    }

def architect_response_review_node(state: SubGraphState):
    # (This function is fine, no changes needed)
    output_to_review = state["architect_response"]
    feedback = interrupt({
        "instruction": "Please respond to the agent... Type 'approve' if you want to proceed with the currently obtained goals, else mention your changes.",
        "content_to_review": output_to_review
    })
    return {'user_response': feedback}

def decision_node(state: SubGraphState):
    # (This function is fine, no changes needed)
    if state['user_response'].lower() == "approve":
        return END
    else:
        return "agent"

def create_architect_agent_graph(checkpointer):
    '''
    this will return the architect agent that will interact with the user to get rigid goals.
    '''
    architect_builder = StateGraph(SubGraphState)
    
    # === REMOVE THE LAMBDA ===
    # The checkpointer is handled by .compile(), not passed into the node.
    architect_builder.add_node("agent", architect_node) 
    
    architect_builder.add_node("review", architect_response_review_node)
    architect_builder.set_entry_point("agent")
    architect_builder.add_edge("agent", "review")
    architect_builder.add_conditional_edges(
        "review",
        decision_node,
        {
            END: END,
            "agent": "agent"
        }
    )

    architect_graph = architect_builder.compile(checkpointer=checkpointer)
    return architect_graph