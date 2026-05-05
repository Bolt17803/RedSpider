# RedSpider 🕷️

An AI-powered multi-agent orchestration framework designed to automate complex development tasks through collaborative autonomous agents. RedSpider enables seamless coordination between specialized agents (Architect, Planner, Coder, Validator, and Summarizer) to transform user requirements into fully executable solutions.

## 🌟 Features

- **Multi-Agent Architecture**: Specialized agents with distinct roles working collaboratively
  - **Architect Agent**: Analyzes requirements and defines project goals
  - **Planner Agent**: Creates detailed implementation plans
  - **Coder Agent**: Generates production-ready code
  - **Validation Agent**: Tests and validates generated code
  - **Summarizer Agent**: Compiles results and documentation

- **Human-in-the-Loop (HITL)**: Interactive interrupts for user approval at critical points
- **Real-Time Streaming**: Live progress updates and token streaming for agent work
- **Project Management**: Track and manage multiple projects with persistent history
- **Multi-Model Support**: Compatible with Ollama (local) and Google Gemini (cloud)
- **Graph-Based Orchestration**: LangGraph-powered agent coordination
- **Modern UI**: React + Next.js frontend with Tailwind CSS styling
- **Production-Ready API**: FastAPI backend with proper error handling and CORS

## 📋 System Architecture

### Workflow Lifecycle

```
User Query
   ↓
Architect Agent (Requirements Analysis & Goal Setting)
   ↓ (Human Review/Approval)
Planner Agent (Detailed Procedure & Planning)
   ↓ (Human Review/Approval)
Coder Agent (Code Generation)
   ↓
Validation Agent (Testing & Quality Checks)
   ↓
Summarizer Agent (Results & Documentation)
   ↓
User Delivery
```

### Project Structure

```
RedSpider/
├── backend/                 # Python FastAPI backend
│   ├── main.py             # Core FastAPI application & API endpoints
│   ├── requirements.txt     # Python dependencies
│   ├── graphs/             # LangGraph orchestration logic
│   ├── nodes/              # Individual agent implementations
│   ├── tools/              # Agent tools and utilities
│   ├── prompts/            # Agent prompts and instructions
│   ├── models/             # Data models and schemas
│   ├── workspace/          # Generated project workspace
│   └── data/               # Data storage and management
├── frontend/               # Next.js React frontend
│   ├── app/               # Next.js pages and layout
│   ├── components/        # React components
│   ├── package.json       # Node.js dependencies
│   └── tailwind.config.ts # Tailwind CSS configuration
└── secret/                # Configuration and blueprint files
    ├── bluprint.txt       # System architecture documentation
    ├── hitl.py           # Human-in-the-loop implementation
    └── supervisor.py     # Workflow supervisor logic
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **Node.js 18+**
- **npm** or **yarn**
- **Environment Variables**: Create a `.env` file in the backend directory

### Backend Setup

1. **Navigate to backend directory:**
```bash
cd backend
```

2. **Create Python virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables** (`.env`):
```env
# LLM Configuration
GOOGLE_API_KEY=your_google_api_key_here

# Project paths
PROJECTS_CSV_PATH=workspace/projects.csv
PLAYGROUND_PATH=workspace/projects

# Optional: Ollama configuration for local LLM
OLLAMA_MODEL=llama2
OLLAMA_BASE_URL=http://localhost:11434
```

5. **Start the backend server:**
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory:**
```bash
cd frontend
```

2. **Install dependencies:**
```bash
npm install
```

3. **Start the development server:**
```bash
npm run dev
```

Frontend will be available at: `http://localhost:3000`

## 📖 Usage Guide

### Starting a Workflow

1. **Access the UI**: Open `http://localhost:3000` in your browser
2. **Enter Project Details**: 
   - Provide a project title
   - Describe your requirements or task
3. **Initial Analysis**: The Architect Agent will analyze your requirements
4. **Review & Approve**: 
   - Review the goals and follow-up questions
   - Provide answers or approve to proceed
5. **Planning Phase**: The Planner Agent creates detailed implementation steps
6. **Implementation**: The Coder Agent generates the code
7. **Validation**: The Validation Agent tests the generated code
8. **Summary**: The Summarizer Agent compiles results

### API Endpoints

#### Initialize Workflow
```bash
POST /workflow/start
Content-Type: application/json

{
  "initial_query": "Create a Python web scraper for news articles",
  "title": "News Scraper Project"
}
```

**Response:**
```json
{
  "agent_output": "...",
  "agent_instruction": "Please review and approve the project goals",
  "thread_id": "uuid-string",
  "agent_node": "architect_agent"
}
```

#### Get Workflow State
```bash
GET /workflow/state/{thread_id}
```

**Response:**
```json
{
  "messages": [...],
  "active_node": "coder_agent",
  "instruction": "...",
  "thread_id": "uuid",
  "status": "running",
  "todos": [...]
}
```

#### Continue Workflow (Resume with Human Input)
```bash
POST /workflow/chat
Content-Type: application/json

{
  "run_id": "uuid-string",
  "query": "approve"
}
```

This uses Server-Sent Events (SSE) for streaming responses.

#### Project Management
```bash
POST /create-project
GET /projects-history
```

## 🔧 Configuration

### Model Selection

**Google Gemini** (Cloud):
```python
# Uses GOOGLE_API_KEY from environment
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-pro")
```

**Ollama** (Local):
```python
# Uses Ollama running locally
from langchain_ollama import OllamaLLM
llm = OllamaLLM(model="llama2")
```

### Customizing Agent Prompts

Edit prompt templates in `backend/prompts/` directory for each agent:
- `architect_prompt.txt`
- `planner_prompt.txt`
- `coder_prompt.txt`
- `validator_prompt.txt`
- `summarizer_prompt.txt`

### Adding Custom Tools

Create tools in `backend/tools/` and register them with agents:
```python
# Example tool
def custom_tool(input_data: str) -> str:
    """Your custom tool implementation"""
    return result

# Register in agent configuration
agent_tools.append(custom_tool)
```

## 🛠️ Development

### Running Tests
```bash
cd backend
python -m pytest test_tester.py -v
```

### Debugging

**Backend Logs:**
```bash
# Check uvicorn output logs
tail -f uvicorn.out
tail -f uvicorn.err
```

**Frontend Development Tools:**
- Use Next.js built-in debugging
- Open browser DevTools (F12) for React debugging

### Agent Visualization

The system generates a workflow graph automatically:
```bash
# Graph saved to backend/graph.png after startup
# Shows the LangGraph orchestration structure
```

## 📊 Dependencies

### Backend (Python)
- **FastAPI** (0.128.0): Modern web framework
- **LangGraph** (1.0.7): Agent orchestration
- **LangChain** (1.2.7): LLM framework
- **DeepAgents** (0.3.9): Advanced agent capabilities
- **Uvicorn** (0.40.0): ASGI server
- **Google GenAI** (4.2.0): Google Gemini integration
- **Ollama** (1.0.1): Local LLM support

### Frontend (Node.js)
- **Next.js** (14.2.0): React framework
- **React** (18.3.1): UI library
- **Tailwind CSS** (3.4.7): Styling
- **TypeScript** (5.5.0): Type safety

## 🔐 Security Considerations

1. **API Keys**: Never commit `.env` files with credentials
2. **CORS**: Configured for localhost development (update for production)
3. **Thread Isolation**: Each workflow has isolated state via thread IDs
4. **Input Validation**: All API inputs validated with Pydantic models

## 📝 Example Workflows

### Example 1: Creating a REST API
```
Query: "Create a REST API for a todo application with authentication"
↓
Architect: Defines endpoints, auth method, database schema
↓
Planner: Creates implementation steps using FastAPI
↓
Coder: Generates FastAPI code with SQLAlchemy models
↓
Validator: Tests endpoints and authentication
↓
Summary: Returns complete, tested API implementation
```

### Example 2: Data Pipeline
```
Query: "Build a data pipeline that processes CSV and generates reports"
↓
Architect: Defines data flow, transformation logic
↓
Planner: Creates Pandas/Polars implementation steps
↓
Coder: Generates data processing code
↓
Validator: Tests with sample data
↓
Summary: Delivers pipeline with documentation
```

## 📚 Project History

The project maintains a CSV file with all created projects:
```
workspace/
├── projects.csv
└── projects/
    ├── [Project Name]/
    │   ├── generated_code/
    │   ├── test_results/
    │   └── documentation/
```

## 🤝 Contributing

This is an active AI research project. Contributions welcome for:
- Additional agent types
- New tool implementations
- Frontend UI improvements
- Performance optimizations
- Documentation enhancements

## 📄 License

Project license information (if applicable)

## 🐛 Troubleshooting

### Backend Won't Start
- Check Python version: `python --version` (need 3.9+)
- Verify all dependencies: `pip list`
- Check port 8000 is available: `lsof -i :8000`

### Frontend Connection Issues
- Verify backend is running on `http://localhost:8000`
- Check CORS configuration in `backend/main.py`
- Clear browser cache and restart dev server

### LLM Connection Issues
- **Gemini**: Verify `GOOGLE_API_KEY` is set correctly
- **Ollama**: Ensure Ollama is running: `ollama serve`

### Workflow Stuck
- Check `uvicorn.err` and `uvicorn.out` logs
- Verify thread_id is valid
- Try resuming workflow with `/workflow/chat` endpoint

### 📞 Support

For issues or questions:
1. Check existing GitHub issues
2. Review logs in backend/uvicorn.err
3. Create detailed issue with workflow state

---

**Built with ❤️ using LangChain, LangGraph, and FastAPI**