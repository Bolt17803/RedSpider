from typing import Any
import os
from pathlib import Path
from deepagents.backends import FilesystemBackend
from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent
from prompts.coder import coder_backstory
from graphs.orchestrator import specialized_subagents
from dotenv import load_dotenv
load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
PLAYGROUND_PATH = os.getenv("PLAYGROUND_PATH")

coder_agent: Any = None
deepagent_llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=0.0,
    convert_system_message_to_human=True,
)

def create_coder_agent(path: str):
    global coder_agent
    root_dir = Path(path).resolve().as_posix()  # Ensure absolute path in POSIX format
    backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    coder_agent = create_deep_agent(
            model=deepagent_llm,
            system_prompt=coder_backstory(),
            backend=backend,
            subagents=specialized_subagents
        )

workspace_path = os.path.join(PLAYGROUND_PATH, "deepagent_test")
os.makedirs(workspace_path, exist_ok=True)
create_coder_agent(workspace_path)

message = """ls /

Write simple FastAPI app to /main.py:
@app.get("/")
def hello(): return {"message": "OCR Pipeline Ready"}
"""
result = coder_agent.invoke({"messages": [{"role": "user", "content": message}]})