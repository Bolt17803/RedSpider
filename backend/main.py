import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from graphs.orchestrator import graph_invoker
from langgraph.types import Command
from fastapi.responses import StreamingResponse
from IPython.display import Image, display

app = FastAPI()

# Allow CORS for Streamlit (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InitRequest(BaseModel):
    initial_query: str

class UserRequest(BaseModel):
    run_id: str
    query: str

@app.on_event("startup")
def startup_event():
    global graph 
    graph = graph_invoker()
    img_bytes = graph.get_graph().draw_mermaid_png()
    with open("graph.png", "wb") as f:
        f.write(img_bytes)


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/workflow/start")
def start_workflow_endpoint(payload: InitRequest):
    thread_id = "main-workflow"
    config = {"configurable": {"thread_id": thread_id}}
    init_state = {
        "user_response": payload.initial_query,
    }
    intermediate_state = graph.invoke(init_state, config)

    if '__interrupt__' in intermediate_state:
        interrupt_data = intermediate_state['__interrupt__']
        interrupt_value = interrupt_data[0].value
        agent_output = interrupt_value['content_to_review']
        agent_instruction = interrupt_value['instruction']
        agent_node = intermediate_state['agent_node']
    else:
        agent_output = None
        agent_instruction = None
    return {"agent_output": agent_output, "agent_instruction": agent_instruction, 'thread_id': thread_id, 'agent_node': agent_node}


@app.post("/workflow/architect_review")
def architect_conversation(user_response: UserRequest):
    try:
        config = {"configurable": {"thread_id": user_response.run_id}}
        state = graph.invoke(
            Command(resume=user_response.query),
            config
        )
        
        if '__interrupt__' in state:
            interrupt_data = state['__interrupt__']
            interrupt_value = interrupt_data[0].value
            agent_output = interrupt_value['content_to_review']
            agent_instruction = interrupt_value['instruction']
            agent_node = state['agent_node']
        else:
            raise Exception("No interrupt found in state.")
        
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"agent_output": agent_output, "agent_instruction": agent_instruction, 'agent_node': agent_node}

@app.post("/workflow/chat")
async def workflow_status(user_response: UserRequest):
    async def event_generator():
        config = {"configurable": {"thread_id": user_response.run_id}}
        
        try:
            # Use astream_events and version "v1"
            async for event in graph.astream_events(
                Command(resume=user_response.query),
                config,
                version="v1" 
            ):
                kind = event["event"]
                
                # Event 1: For streaming agents (like your planner_agent)
                if kind == "on_chat_model_stream":
                    chunk_content = event["data"]["chunk"].content
                    if chunk_content:
                        # Yield the token as a JSON object
                        yield json.dumps({"token": chunk_content}) + "\n"
                
                # Event 2: For interrupting agents (like your architect_agent)
                elif kind == "on_interrupt":
                    # This event is triggered by your 'architect_review_node'
                    # The architect's full response is inside 'content_to_review'
                    interrupt_data = event["data"]["output"][0].value
                    content_to_review = interrupt_data.get("content_to_review")
                    
                    if content_to_review:
                        # Yield the entire formatted response as a single "token"
                        yield json.dumps({"token": content_to_review}) + "\n"

        except Exception as e:
            print(f"Error in stream: {e}")
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
    #     config = {"configurable": {"thread_id": user_response.run_id}}
    #     state = graph.invoke(
    #         Command(resume=user_response.query),
    #         config
    #     )
    #     if state['agent_node'] == 'architect':
    #         agent_response = state['architect_response']
    #     else:
    #         agent_response = state['planner_response']
    # except Exception as e:
    #     raise HTTPException(status_code=404, detail=str(e))
    # return {"agent_response": agent_response}    
