import os
import json
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from googlesearch import search

# Load environment variables
load_dotenv()

# Initialize the Gemini Client
client = genai.Client()

PROFILE_FILE = "bike_profile.json"

# Helper functions for JSON storage
def load_bike_profile() -> dict:
    if not os.path.exists(PROFILE_FILE):
        # Default fallback structure
        return {"make": "Generic", "model": "Bike", "year": 2020, "current_mileage": 0, "last_oil_change_mileage": 0}
    with open(PROFILE_FILE, "r") as f:
        return json.load(f)

def save_bike_profile(data: dict):
    with open(PROFILE_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Tool 1: Maintenance Status
def check_my_bike_service_status() -> str:
    """Checks the maintenance and service schedule logs for the rider's active motorcycle profile."""
    bike = load_bike_profile()
    mileage_since_oil = bike["current_mileage"] - bike["last_oil_change_mileage"]
    km_remaining = 5000 - mileage_since_oil
    
    if mileage_since_oil >= 5000:
        return f"System Log: The {bike['make']} is overdue for an oil change by {abs(km_remaining)} km."
    return f"System Log: The oil is currently fine. {km_remaining} km left until the next change."

# Tool 2: Web Search
def search_web_for_motorcycle_specs(query: str) -> str:
    """Searches Google for mechanical specifications, fluid capacities, or torque specs for motorcycles."""
    try:
        results = []
        for url in search(query, num_results=3):
            results.append(url)
        return f"Search successful. Found specs at: {', '.join(results)}. Summarize this fact for the user."
    except Exception as e:
        return f"Search failed: {str(e)}"

# --- STREAMLIT WEB INTERFACE CONFIG ---
st.set_page_config(page_title="MotoMechanic AI Portal", page_icon="🏍️", layout="wide")

# Load current bike configuration
bike_data = load_bike_profile()

# 1. Create a Sidebar Dashboard
st.sidebar.title("🏍️ Garage Profile")
st.sidebar.markdown(f"### **{bike_data['year']} {bike_data['make']} {bike_data['model']}**")
st.sidebar.divider()

# Interactive Odometer Updater Widget right in the sidebar
st.sidebar.markdown(f"**Current Odometer:** `{bike_data['current_mileage']} km`")
st.sidebar.markdown(f"**Last Oil Change:** `{bike_data['last_oil_change_mileage']} km`")

st.sidebar.subheader("Update Mileage Log")
new_mileage = st.sidebar.number_input("Enter new odometer reading (km):", min_value=bike_data['current_mileage'], value=bike_data['current_mileage'])
if st.sidebar.button("Save New Mileage"):
    bike_data['current_mileage'] = new_mileage
    save_bike_profile(bike_data)
    st.sidebar.success(f"Saved! Odometer logged at {new_mileage} km.")
    st.rerun()

# 2. Setup Persistent Chat Session Memory across UI reloads
if "chat" not in st.session_state:
    system_instruction = f"""
    You are 'MotoMechanic AI', an expert motorcycle technician. 
    You are talking to a rider who owns a {bike_data['year']} {bike_data['make']} {bike_data['model']}.

    You have two custom tools available:
    1. `check_my_bike_service_status`: Use this to check the user's current mileage logs.
    2. `search_web_for_motorcycle_specs`: Use this if the user asks for specs requiring online lookups.

    Safety Rule: Always tell the user to check their factory service manual for structural engine or brake repairs.
    """
    st.session_state.chat = client.chats.create(
        model='gemini-2.5-flash',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[check_my_bike_service_status, search_web_for_motorcycle_specs], 
            temperature=0.7
        )
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

# Main App Header Text
st.title("🤖 MotoMechanic AI Assistant")
st.caption("Ask maintenance questions, check service schedules, or request torque specs live!")

# Display current chat history on screen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["text"])

# Handle new inputs from user chat input box
if user_prompt := st.chat_input("Type your message here..."):
    # Render user message
    with st.chat_message("user"):
        st.write(user_prompt)
    st.session_state.messages.append({"role": "user", "text": user_prompt})

    # Render assistant response with a spinner
    with st.chat_message("assistant"):
        with st.spinner("Mechanic is checking specifications..."):
            response = st.session_state.chat.send_message(user_prompt)
            st.write(response.text)
    st.session_state.messages.append({"role": "assistant", "text": response.text})