from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from graphs.orchestrator import graph_invoker
from langgraph.types import Command
from fastapi.responses import StreamingResponse

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
    else:
        agent_output = None
        agent_instruction = None
    return {"agent_output": agent_output, "agent_instruction": agent_instruction, 'thread_id': thread_id}


@app.post("/workflow/chat")
def workflow_status(user_response: UserRequest):
    try:
        config = {"configurable": {"thread_id": user_response.run_id}}
        state = graph.invoke(
            Command(resume=user_response.query),
            config
        )
        if state['agent_node'] == 'architect':
            agent_response = state['architect_response']
        else:
            agent_response = state['planner_response']
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"agent_response": agent_response}    
