# Project Summary: Simple FastAPI App

## Overview of Implemented Features
A simple FastAPI application has been implemented. It exposes a single GET endpoint at the root path (`/`) which returns a JSON response: `{"message": "OCR Pipeline Ready"}`.

## File Structure
```
/
└── main.py
```

## Setup Instructions
1. **Install Python**: Ensure you have Python 3.7+ installed.
2. **Install dependencies**:
   ```bash
   pip install fastapi uvicorn
   ```

## Execution Instructions
1. **Run the application**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
2. **Access the API**:
   Open your web browser or use a tool like `curl` to access the endpoint:
   ```bash
   curl http://localhost:8000/
   ```
   You should see the response: `{"message": "OCR Pipeline Ready"}`
