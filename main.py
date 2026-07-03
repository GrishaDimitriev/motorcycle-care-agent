import os
import sqlite3
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from googlesearch import search
from PIL import Image

# Load environment variables
load_dotenv()

# Initialize the Gemini Client
client = genai.Client()

DB_FILE = "garage.db"

# =====================================================================
# I. DATABASE ENGINE
# =====================================================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 1. Create the base table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            current_mileage INTEGER NOT NULL,
            last_oil_change_mileage INTEGER NOT NULL,
            is_active INTEGER DEFAULT 0
        )
    """)
    
    # 2. Schema Migration: Automatically add the 'color' column if it's missing
    cursor.execute("PRAGMA table_info(vehicles)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'color' not in columns:
        cursor.execute("ALTER TABLE vehicles ADD COLUMN color TEXT DEFAULT 'Black'")
        conn.commit()

    # Seed initial bike asset if empty
    cursor.execute("SELECT COUNT(*) FROM vehicles")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO vehicles (make, model, year, current_mileage, last_oil_change_mileage, color, is_active)
            VALUES ('Kawasaki', 'Ninja 250R', 2008, 45000, 40000, 'Black', 1)
        """)
    conn.commit()
    conn.close()

init_db()

def get_active_vehicle() -> dict:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"id": 1, "make": "Kawasaki", "model": "Ninja 250R", "year": 2008, "current_mileage": 45000, "last_oil_change_mileage": 40000, "color": "Black"}

def get_all_vehicles() -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_active_vehicle(vehicle_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE vehicles SET is_active = 0")
    cursor.execute("UPDATE vehicles SET is_active = 1 WHERE id = ?", (vehicle_id,))
    conn.commit()
    conn.close()

def add_new_vehicle(make: str, model: str, year: int, mileage: int, last_oil: int, color: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE vehicles SET is_active = 0")
    cursor.execute("""
        INSERT INTO vehicles (make, model, year, current_mileage, last_oil_change_mileage, color, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (make, model, year, mileage, last_oil, color))
    conn.commit()
    conn.close()

def update_mileage_in_db(vehicle_id: int, new_mileage: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE vehicles SET current_mileage = ? WHERE id = ?", (new_mileage, vehicle_id))
    conn.commit()
    conn.close()

def update_vehicle_details(vehicle_id: int, make: str, model: str, year: int, color: str):
    """Updates the core text attributes of an existing vehicle row record."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE vehicles 
        SET make = ?, model = ?, year = ?, color = ? 
        WHERE id = ?
    """, (make, model, year, color, vehicle_id))
    conn.commit()
    conn.close()

# =====================================================================
# II. TOOLS
# =====================================================================
def check_my_bike_service_status() -> str:
    """Checks the maintenance and service schedule logs for the rider's active motorcycle profile."""
    bike = get_active_vehicle()
    mileage_since_oil = bike["current_mileage"] - bike["last_oil_change_mileage"]
    km_remaining = 5000 - mileage_since_oil
    
    if mileage_since_oil >= 5000:
        return f"System Log: The {bike['color']} {bike['make']} {bike['model']} is overdue for an oil change by {abs(km_remaining)} km."
    return f"System Log: The oil is fine. {km_remaining} km left until the next change."

def search_web_for_motorcycle_specs(query: str) -> str:
    """Searches Google for mechanical specifications, fluid capacities, or torque specs for motorcycles."""
    try:
        results = []
        for url in search(query, num_results=3):
            results.append(url)
        return f"Search successful. Found specs at these URLs: {', '.join(results)}. Please summarize these facts clearly for the user."
    except Exception as e:
        return f"Search failed due to an error: {str(e)}"

# =====================================================================
# III. STREAMLIT INTERFACE
# =====================================================================
st.set_page_config(page_title="MotoMechanic Enterprise Portal", page_icon="🏍️", layout="wide")

# Fetch fresh data
active_bike = get_active_vehicle()
all_bikes = get_all_vehicles()

# Sidebar Setup
st.sidebar.title("🏢 Enterprise Garage")

bike_options = {f"{b['year']} {b['make']} {b['model']}": b['id'] for b in all_bikes}

current_index = 0
active_bike_string = f"{active_bike['year']} {active_bike['make']} {active_bike['model']}"
if active_bike_string in bike_options:
    current_index = list(bike_options.keys()).index(active_bike_string)

selected_bike_name = st.sidebar.selectbox(
    "Select Active Vehicle Focus:", 
    list(bike_options.keys()), 
    index=current_index
)

if bike_options[selected_bike_name] != active_bike['id']:
    set_active_vehicle(bike_options[selected_bike_name])
    if "chat" in st.session_state:
        del st.session_state.chat
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown(f"### Current Focus: **{active_bike['year']} {active_bike['make']} {active_bike['model']}**")
st.sidebar.markdown(f"🎨 **Color:** `{active_bike.get('color', 'Black')}`")
st.sidebar.markdown(f"📊 **Odometer:** `{active_bike['current_mileage']} km`")
st.sidebar.markdown(f"🔧 **Last Service:** `{active_bike['last_oil_change_mileage']} km`")

new_mileage = st.sidebar.number_input(
    "Log kilometers ridden:", 
    min_value=active_bike['current_mileage'], 
    value=active_bike['current_mileage']
)
if st.sidebar.button("Update Odometer"):
    update_mileage_in_db(active_bike['id'], new_mileage)
    st.sidebar.success("Odometer updated!")
    st.rerun()

st.sidebar.divider()

# NEW: Expandable Bike Editor Form Tool Panel
with st.sidebar.expander("📝 Edit Current Bike Details"):
    edit_make = st.text_input("Manufacturer:", value=active_bike['make'])
    edit_model = st.text_input("Model Name:", value=active_bike['model'])
    edit_year = st.number_input("Year Configuration:", min_value=1900, max_value=2028, value=active_bike['year'])
    edit_color = st.text_input("Bike Color:", value=active_bike.get('color', 'Black'))
    
    if st.button("Save Changes"):
        update_vehicle_details(active_bike['id'], edit_make, edit_model, edit_year, edit_color)
        st.success("Bike specifications updated!")
        if "chat" in st.session_state:
            del st.session_state.chat
        st.rerun()

# Expandable Form to park a brand new bike
with st.sidebar.expander("➕ Park New Bike in Garage"):
    new_make = st.text_input("Manufacturer (e.g., Honda):")
    new_model = st.text_input("Model (e.g., CB500X):")
    new_year = st.number_input("Year:", min_value=1900, max_value=2028, value=2022)
    new_color = st.text_input("Color (e.g., Red):", value="Black")
    new_odo = st.number_input("Current Mileage (km):", min_value=0, value=12000)
    new_oil = st.number_input("Mileage at Last Oil Change (km):", min_value=0, value=10000)
    
    if st.button("Add to Garage Database"):
        if new_make and new_model:
            add_new_vehicle(new_make, new_model, new_year, new_odo, new_oil, new_color)
            st.success("Parked in your garage!")
            if "chat" in st.session_state:
                del st.session_state.chat
            st.rerun()
        else:
            st.error("Please provide both Manufacturer and Model.")

st.sidebar.divider()
st.sidebar.subheader("📷 Visual Diagnostics")
uploaded_file = st.sidebar.file_uploader(
    "Upload photo asset for component wear evaluation:", 
    type=["jpg", "jpeg", "png"]
)

if uploaded_file:
    st.sidebar.image(uploaded_file, caption="Staged Inspection Asset", use_container_width=True)

# =====================================================================
# IV. CHAT SESSION CONTROLLER
# =====================================================================
if "chat" not in st.session_state or "current_bike_id" not in st.session_state or st.session_state.current_bike_id != active_bike['id']:
    st.session_state.current_bike_id = active_bike['id']
    
    system_instruction = f"You are 'MotoMechanic AI', a professional motorcycle diagnostic service agent. You are evaluating maintenance data for a user who owns a {active_bike.get('color', 'Black')} {active_bike['year']} {active_bike['make']} {active_bike['model']}. You have access to two custom diagnostic Python tool operations: 1. check_my_bike_service_status to calculate service thresholds against their SQLite mileage records, and 2. search_web_for_motorcycle_specs if you require external lookup specs. You are fully multimodal. If the user presents an image asset, perform a rigorous visual mechanical diagnostic check. Safety Rule: Always instruct the user to verify guidelines inside their official factory service manuals."
    
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

# =====================================================================
# V. MAIN WINDOW RENDER LAYER
# =====================================================================
st.title("🤖 MotoMechanic Enterprise AI Portal")
st.caption(f"Connected Core Service Terminal | Active Unit Target: {active_bike['year']} {active_bike['make']} {active_bike['model']}")

# Render historical logs down the page
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["text"])

# Get inputs
if user_prompt := st.chat_input("Ask a diagnostic or maintenance question..."):
    with st.chat_message("user"):
        st.write(user_prompt)
    st.session_state.messages.append({"role": "user", "text": user_prompt})

    with st.chat_message("assistant"):
        with st.spinner("Processing framework diagnostic tool pipelines..."):
            if uploaded_file:
                img = Image.open(uploaded_file)
                response = st.session_state.chat.send_message([user_prompt, img])
            else:
                response = st.session_state.chat.send_message(user_prompt)
            st.write(response.text)
            
    st.session_state.messages.append({"role": "assistant", "text": response.text})