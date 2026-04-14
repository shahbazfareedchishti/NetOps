import streamlit as st
import requests

# The address of your internal FastAPI brain
API_URL = "http://localhost:8000/chat"

st.set_page_config(page_title="NetOps Co-Pilot", page_icon="📡", layout="centered")
st.title("📡 NetOps AI Co-Pilot")
st.markdown("Ask me anything about Border Gateway Protocol (BGP).")

# Initialize chat history in Streamlit's session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if user_question := st.chat_input("E.g., What is a Keepalive message?"):
    
    # 1. Display user message in UI
    st.chat_message("user").markdown(user_question)
    st.session_state.messages.append({"role": "user", "content": user_question})

    # 2. Send the question to your FastAPI backend
    with st.chat_message("assistant"):
        with st.spinner("Analyzing network documentation..."):
            try:
                response = requests.post(
                    API_URL, 
                    json={"question": user_question},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "Error: No answer returned.")
                    sources = data.get("sources_analyzed", 0)
                    
                    # Add a small note about how many documents were checked
                    full_response = f"{answer}\n\n*(Analyzed {sources} technical chunks)*"
                    
                    st.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                else:
                    st.error(f"Backend Error: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                st.error("API Offline: Could not connect to the NetOps Brain. Is Uvicorn running?")