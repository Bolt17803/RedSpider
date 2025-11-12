import streamlit as st
import requests
import json

# FastAPI backend URL
BACKEND_BASE = "http://localhost:8000"

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# thread_id is returned from /workflow/start and used for subsequent calls
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

if "agent_node" not in st.session_state:
    st.session_state.agent_node = None

if 'architect' not in st.session_state:
    st.session_state.architect = None

if 'planner' not in st.session_state:
    st.session_state.planner = None

if st.session_state.architect is None:
    st.session_state.architect = True
    st.session_state.planner = False

st.title("Chatbot Application")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("Type your message here..."):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    if prompt=="approve" and st.session_state.architect:
        st.session_state.planner = True
        st.session_state.architect = False

    # Add to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Determine whether this is the first message in the thread
    if st.session_state.thread_id is None:
        # Start a new workflow
        payload = {"initial_query": prompt}
        endpoint = f"{BACKEND_BASE}/workflow/start"
        with st.spinner("Starting workflow..."):
            try:
                response = requests.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                # store thread_id for subsequent calls
                st.session_state.thread_id = data.get("thread_id")

                # Show agent_output and instructions if present
                agent_output = data.get("agent_output")
                agent_instruction = data.get("agent_instruction")
                agent_node = data.get("agent_node")
                if agent_output:
                    with st.chat_message("assistant"):
                        st.markdown(agent_output)
                    st.session_state.messages.append({"role": "assistant", "content": agent_output})
                if agent_instruction:
                    st.info(f"Agent instruction: {agent_instruction}")
                st.session_state.agent_node = agent_node
            except requests.exceptions.RequestException as e:
                st.error(f"Error starting workflow: {str(e)}")
    elif st.session_state.thread_id is not None and st.session_state.architect:
        # Continue the architect review workflow
        payload = {"run_id": st.session_state.thread_id, "query": prompt}
        endpoint = f"{BACKEND_BASE}/workflow/architect_review"
        with st.spinner("Continuing architect review..."):
            try:
                response = requests.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                agent_output = data.get("agent_output")
                agent_instruction = data.get("agent_instruction")
                agent_node = data.get("agent_node")
                if agent_output:
                    with st.chat_message("assistant"):
                        st.markdown(agent_output)
                    st.session_state.messages.append({"role": "assistant", "content": agent_output})
                if agent_instruction:
                    st.info(f"Agent instruction: {agent_instruction}")
                st.session_state.agent_node = agent_node
            except requests.exceptions.RequestException as e:
                st.error(f"Error continuing architect review: {str(e)}")
    else:
        # Continue an existing workflow (NOW WITH STREAMING)
        payload = {"run_id": st.session_state.thread_id, "query": prompt}
        endpoint = f"{BACKEND_BASE}/workflow/chat"
        
        with st.chat_message("assistant"):
            # Create a placeholder to stream output into
            placeholder = st.empty()
            full_response = ""
            
            try:
                # Use requests.post with stream=True
                with requests.post(endpoint, json=payload, stream=True, timeout=600) as response:
                    response.raise_for_status()
                    
                    # Iterate over the response line by line
                    for line in response.iter_lines():
                        if line:
                            try:
                                # Decode the line and parse the JSON
                                data_str = line.decode('utf-8')
                                data = json.loads(data_str)
                                
                                if "error" in data:
                                    st.error(f"Backend error: {data['error']}")
                                    full_response = f"Backend error: {data['error']}"
                                    break
                                
                                token = data.get("token")
                                if token:
                                    full_response += token
                                    # Update the placeholder with the accumulating response
                                    placeholder.markdown(full_response + "▌") # ▌ adds a cursor
                                    
                            except json.JSONDecodeError:
                                # Skip lines that aren't valid JSON
                                pass
                                
            except requests.exceptions.RequestException as e:
                st.error(f"Error continuing workflow: {str(e)}")
                full_response = f"Error: {str(e)}"
            
            # Write the final response without the cursor
            placeholder.markdown(full_response)
            
            # Add the final, complete response to the session history
            if full_response:
                st.session_state.messages.append({"role": "assistant", "content": full_response})
