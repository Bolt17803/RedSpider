from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

# Define write_email tool
@tool
def write_email(to: str, topic: str) -> str:
    """write an email (requires human approval)."""
    print("using write email tool")

    # Create a prompt for the email draft
    prompt = f"""You are an email drafting assistant. Create a professional email body based on the topic provided.
    
    Topic: {topic}
    
    Please draft a professional email body."""
    
    response = llm.invoke(prompt)
    body = response.content
    
    # Return the draft for approval
    return f"To: {to}\nSubject: {topic}\n\nBody:\n{body}"

# Create supervisor with HITL middleware
supervisor = create_agent(
    model=llm,
    tools=[write_email],
    system_prompt="""You are a supervisor that coordinates email tasks. 
    For any email request, you should use the write_email tool to draft an email.
    After getting the draft, you should request human approval and make changes if needed.""",
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={"write_email": True},
            description_prefix="Email draft pending approval",
            interrupt_after_tool_execution=True  # This makes it interrupt after the tool runs
        )
    ],
    checkpointer=InMemorySaver()  # Required!
)

# Usage
config = {"configurable": {"thread_id": "thread_1"}}

# Run until interrupt
result = supervisor.invoke(
    {"messages": [{"role": "user", "content": "write an email to ko@gmail.com about the leave intimation becasue of my marriage"}]},
    config
)

# Check for interrupt
if result.get("__interrupt__"):
    interrupt = result["__interrupt__"][0].value
    action_request = interrupt['action_requests'][0]
    to_addr = action_request['args']['to']
    topic = action_request['args']['topic']
    
    # Get the email draft from the tool's output
    tool_output = interrupt.get('tool_output', '')
    print("\nEmail Draft for Review:")
    print("----------------------")
    print(tool_output)  # This will show the actual email draft
    print("----------------------")

    decision = input("\nDo you want to approve (a), edit (e), or reject (r) this email? ").lower()

    if decision == "a":
        print("\nApproving email...")
        result = supervisor.invoke(
                Command(resume={"decisions": [{"type": "approve"}]}), 
                config
            )
    elif decision == "e":
        new_topic = input("Enter new topic for the email: ")
        print("\nGenerating new draft...")
        edited = {
            "name": "write_email",
            "args": {
                "to": to_addr,
                "topic": new_topic
            }
        }
        result = supervisor.invoke(
            Command(resume={"decisions": [{"type": "edit", "edited_action": edited}]}), 
            config
        )
    else:
        print("\nRejecting email...")
        result = supervisor.invoke(
            Command(resume={"decisions": [{"type": "reject", "message": "Email rejected by user"}]}), 
            config
        )
        
    # Process the messages from the result
    messages = result.get('messages', [])
    if messages:
        # Find the tool message (email draft)
        tool_message = next((msg for msg in messages 
                           if hasattr(msg, 'name') and msg.name == 'write_email'), None)
        if tool_message:
            print("\nEmail Content:")
            print("----------------------")
            print(tool_message.content)
            print("----------------------")
        
        # Find the last AI message (summary)
        last_ai_message = next((msg for msg in reversed(messages) 
                              if hasattr(msg, '__class__') and msg.__class__.__name__ == 'AIMessage' 
                              and hasattr(msg, 'content') and msg.content), None)
        if last_ai_message:
            print("\nFinal Status:", last_ai_message.content)
    print('---------------------------')
    print(messages)
else:
    # Process direct AI response (non-email cases)
    messages = result.get('messages', [])
    print(result)
    if messages:
        # Find the last AI message
        ai_message = next((msg for msg in reversed(messages) 
                         if hasattr(msg, '__class__') and msg.__class__.__name__ == 'AIMessage' 
                         and hasattr(msg, 'content') and msg.content), None)
        if ai_message:
            print("\nAI Response:", ai_message.content)