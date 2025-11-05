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
                if agent_output:
                    with st.chat_message("assistant"):
                        st.markdown(agent_output)
                    st.session_state.messages.append({"role": "assistant", "content": agent_output})
                if agent_instruction:
                    st.info(f"Agent instruction: {agent_instruction}")

            except requests.exceptions.RequestException as e:
                st.error(f"Error starting workflow: {str(e)}")
    else:
        # Continue an existing workflow
        payload = {"run_id": st.session_state.thread_id, "query": prompt}
        endpoint = f"{BACKEND_BASE}/workflow/chat"
        with st.spinner("Continuing workflow..."):
            try:
                response = requests.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                agent_response = data.get("agent_response")
                if agent_response:
                    with st.chat_message("assistant"):
                        st.markdown(agent_response)
                    st.session_state.messages.append({"role": "assistant", "content": agent_response})
            except requests.exceptions.RequestException as e:
                st.error(f"Error continuing workflow: {str(e)}")