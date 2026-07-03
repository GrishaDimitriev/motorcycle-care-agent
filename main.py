import os
import sqlite3
import time
import streamlit as st
import pandas as pd
from datetime import datetime
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
IMAGE_DIR = "static/inspection_images"

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# =====================================================================
# I. DATABASE CORE INFRASTRUCTURE
# =====================================================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Vehicles core profile parameters
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            current_mileage INTEGER NOT NULL,
            last_oil_change_mileage INTEGER NOT NULL,
            color TEXT DEFAULT 'Black',
            is_active INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("PRAGMA table_info(vehicles)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'color' not in columns:
        cursor.execute("ALTER TABLE vehicles ADD COLUMN color TEXT DEFAULT 'Black'")
        conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            service_type TEXT NOT NULL,
            mileage INTEGER NOT NULL,
            date_logged TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cost REAL DEFAULT 0.0,
            notes TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fuel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            mileage INTEGER NOT NULL,
            liters REAL NOT NULL,
            cost REAL NOT NULL,
            date_logged TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visual_inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            mileage INTEGER NOT NULL,
            date_logged TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            label TEXT NOT NULL,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id) ON DELETE CASCADE
        )
    """)

    # SCHEMA MIGRATION: Drop the old legacy table structure if it's missing the vehicle relationship column
    cursor.execute("PRAGMA table_info(rag_stores)")
    rag_columns = [col[1] for col in cursor.fetchall()]
    if rag_columns and 'vehicle_id' not in rag_columns:
        cursor.execute("DROP TABLE rag_stores")
        conn.commit()

    # Recreate the modernized multi-manual tracking matrix
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rag_stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER UNIQUE NOT NULL,
            store_name TEXT NOT NULL,
            file_name TEXT NOT NULL,
            date_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM vehicles")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO vehicles (make, model, year, current_mileage, last_oil_change_mileage, color, is_active)
            VALUES ('Kawasaki', 'Ninja 250R', 2008, 45000, 40000, 'Black', 1)
        """)
        conn.commit()
        cursor.execute("""
            INSERT INTO service_records (vehicle_id, service_type, mileage, cost, notes)
            VALUES (1, 'Routine Oil Change', 40000, 45.00, 'Swapped out filter and added 10W-40 semi-synthetic oil.')
        """)
        cursor.execute("INSERT INTO fuel_logs (vehicle_id, mileage, liters, cost) VALUES (1, 44200, 10.0, 20.00)")
        cursor.execute("INSERT INTO fuel_logs (vehicle_id, mileage, liters, cost) VALUES (1, 44500, 12.0, 24.00)")
        cursor.execute("INSERT INTO fuel_logs (vehicle_id, mileage, liters, cost) VALUES (1, 44850, 11.5, 23.00)")
        cursor.execute("INSERT INTO fuel_logs (vehicle_id, mileage, liters, cost) VALUES (1, 45000, 5.0, 11.00)")
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
    return dict(row) if row else {"id": 1, "make": "Kawasaki", "model": "Ninja 250R", "year": 2008, "current_mileage": 45000, "last_oil_change_mileage": 40000, "color": "Black"}

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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE vehicles SET make = ?, model = ?, year = ?, color = ? WHERE id = ?", (make, model, year, color, vehicle_id))
    conn.commit()
    conn.close()

def log_service_event(vehicle_id: int, service_type: str, mileage: int, cost: float, notes: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO service_records (vehicle_id, service_type, mileage, cost, notes) VALUES (?, ?, ?, ?, ?)", (vehicle_id, service_type, mileage, cost, notes))
    if "oil" in service_type.lower():
        cursor.execute("UPDATE vehicles SET last_oil_change_mileage = ? WHERE id = ?", (mileage, vehicle_id))
    conn.commit()
    conn.close()

def get_service_history(vehicle_id: int) -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM service_records WHERE vehicle_id = ? ORDER BY mileage DESC", (vehicle_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def log_fuel_event(vehicle_id: int, mileage: int, liters: float, cost: float):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO fuel_logs (vehicle_id, mileage, liters, cost) VALUES (?, ?, ?, ?)", (vehicle_id, mileage, liters, cost))
    cursor.execute("SELECT current_mileage FROM vehicles WHERE id = ?", (vehicle_id,))
    current_odo = cursor.fetchone()[0]
    if mileage > current_odo:
        cursor.execute("UPDATE vehicles SET current_mileage = ? WHERE id = ?", (mileage, vehicle_id))
    conn.commit()
    conn.close()

def get_fuel_history(vehicle_id: int) -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fuel_logs WHERE vehicle_id = ? ORDER BY mileage ASC", (vehicle_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def log_visual_inspection(vehicle_id: int, file_path: str, mileage: int, label: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO visual_inspections (vehicle_id, file_path, mileage, label) VALUES (?, ?, ?, ?)", (vehicle_id, file_path, mileage, label))
    conn.commit()
    conn.close()

def get_visual_inspections(vehicle_id: int) -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM visual_inspections WHERE vehicle_id = ? ORDER BY mileage DESC", (vehicle_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_indexed_rag_store_for_vehicle(vehicle_id: int) -> str:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT store_name FROM rag_stores WHERE vehicle_id = ?", (vehicle_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""

def log_indexed_rag_store_for_vehicle(vehicle_id: int, store_name: str, file_name: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO rag_stores (vehicle_id, store_name, file_name) VALUES (?, ?, ?)", (vehicle_id, store_name, file_name))
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

active_bike = get_active_vehicle()
all_bikes = get_all_vehicles()

# Sidebar Setup
st.sidebar.title("🏢 Enterprise Garage")
bike_options = {f"{b['year']} {b['make']} {b['model']}": b['id'] for b in all_bikes}

current_index = 0
active_bike_string = f"{active_bike['year']} {active_bike['make']} {active_bike['model']}"
if active_bike_string in bike_options:
    current_index = list(bike_options.keys()).index(active_bike_string)

selected_bike_name = st.sidebar.selectbox("Select Active Vehicle Focus:", list(bike_options.keys()), index=current_index)

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

new_mileage = st.sidebar.number_input("Log kilometers ridden:", min_value=active_bike['current_mileage'], value=active_bike['current_mileage'])
if st.sidebar.button("Update Odometer"):
    update_mileage_in_db(active_bike['id'], new_mileage)
    st.sidebar.success("Odometer updated!")
    st.rerun()

st.sidebar.divider()

# DYNAMIC ROADMAP PORTAL EXPANDER
st.sidebar.subheader("📖 Profile Shop Manual RAG")
expected_manual_path = f"manuals/{active_bike['id']}/service_manual.pdf"
active_rag_store = get_indexed_rag_store_for_vehicle(active_bike['id'])

if not active_rag_store:
    if os.path.exists(expected_manual_path):
        st.sidebar.warning(f"Manual detected for target profile index {active_bike['id']} but not indexed yet.")
        if st.sidebar.button("⚡ Index Profile Manual"):
            with st.sidebar.spinner("Uploading separate vehicle context schema into cloud store..."):
                try:
                    store = client.file_search_stores.create(
                        config={
                            "display_name": f"manual-vehicle-id-{active_bike['id']}",
                            "embedding_model": "models/gemini-embedding-2"
                        }
                    )
                    operation = client.file_search_stores.upload_to_file_search_store(
                        file_search_store_name=store.name,
                        file=expected_manual_path,
                        config={"display_name": f"Manual Bike {active_bike['id']}"}
                    )
                    while not operation.done:
                        time.sleep(3)
                        operation = client.operations.get(operation=operation)
                        
                    log_indexed_rag_store_for_vehicle(active_bike['id'], store.name, "service_manual.pdf")
                    st.sidebar.success(f"Manual verified for active profile node!")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Ingestion crashed: {str(e)}")
    else:
        st.sidebar.info(f"Drop this bike's unique manual PDF inside `{expected_manual_path}` to map context index profiles.")
else:
    st.sidebar.success(f"🟢 Active Context: Loaded for Vehicle ID {active_bike['id']}")
    st.sidebar.caption(f"Index Token: `{active_rag_store.split('/')[-1]}`")

st.sidebar.divider()

with st.sidebar.expander("⛽ Log Fuel Refueling Fillup"):
    fuel_mileage = st.number_input("Odometer reading at gas station (km):", min_value=0, value=active_bike['current_mileage'])
    fuel_liters = st.number_input("Total liters filled:", min_value=0.0, value=10.0, step=1.0)
    fuel_cost = st.number_input("Total receipt cost ($):", min_value=0.0, value=20.0, step=1.0)
    if st.button("Log Fuel Data"):
        log_fuel_event(active_bike['id'], fuel_mileage, fuel_liters, fuel_cost)
        st.sidebar.success("Refueling receipt saved!")
        st.rerun()

with st.sidebar.expander("🛠️ Log a New Service Event"):
    service_type = st.selectbox("Job Type:", ["Routine Oil Change", "Brake Pad Flush", "Chain Service", "Tire Replacement", "General Inspection", "Custom Repair"])
    log_mileage = st.number_input("Performed at Mileage (km):", min_value=0, value=active_bike['current_mileage'])
    log_cost = st.number_input("Total Parts/Labor Cost ($):", min_value=0.0, value=0.0, step=5.0)
    log_notes = st.text_area("Mechanic Notes:")
    if st.button("Commit Log Entry"):
        log_service_event(active_bike['id'], service_type, log_mileage, log_cost, log_notes)
        st.sidebar.success("Maintenance event saved!")
        st.rerun()

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

st.sidebar.divider()
st.sidebar.subheader("📷 Visual Diagnostics")
uploaded_file = st.sidebar.file_uploader("Upload component photo asset:", type=["jpg", "jpeg", "png"])
inspection_label = st.sidebar.text_input("Component Label:", value="Component Photo")

if uploaded_file:
    st.sidebar.image(uploaded_file, caption="Staged Inspection Asset", use_container_width=True)


# =====================================================================
# IV. CHAT CONTROLLER WITH FILE SEARCH INTEGRATION
# =====================================================================
if "chat" not in st.session_state or "current_bike_id" not in st.session_state or st.session_state.current_bike_id != active_bike['id']:
    st.session_state.current_bike_id = active_bike['id']
    
    system_instruction = f"""You are 'MotoMechanic AI', a professional motorcycle diagnostic service agent. You are evaluating maintenance data for a user who owns a {active_bike.get('color', 'Black')} {active_bike['year']} {active_bike['make']} {active_bike['model']}.

    If a File Search store is available, use it to lookup exact engineering parameters or torque values from this exact bike's specific manual.
    Otherwise, fall back to check_my_bike_service_status or search_web_for_motorcycle_specs if required.

    Safety Rule: Always instruct the user to verify guidelines inside their official factory service manuals."""
    
    available_tools = [check_my_bike_service_status, search_web_for_motorcycle_specs]
    
    if active_rag_store:
        file_search_tool = types.Tool(
            file_search=types.FileSearch(
                file_search_retrieval_resources=[
                    types.FileSearchRetrievalResource(
                        file_search_store_name=active_rag_store
                    )
                ]
            )
        )
        available_tools.append(file_search_tool)
    
    st.session_state.chat = client.chats.create(
        model='gemini-2.5-flash',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=available_tools, 
            temperature=0.7
        )
    )

if "messages" not in st.session_state:
    st.session_state.messages = []


# =====================================================================
# V. MAIN WINDOW LAYOUT
# =====================================================================
st.title("🤖 MotoMechanic Enterprise AI Portal")
st.caption(f"Connected Core Service Terminal | Active Unit Target: {active_bike['year']} {active_bike['make']} {active_bike['model']}")

tab_chat, tab_service, tab_analytics = st.tabs(["💬 Mechanic Chat", "📋 Service History", "📊 Cost Metrics"])

with tab_chat:
    with st.expander("🚨 Open Engine Troubleshooting Diagnostic Wizard"):
        st.write("Isolate electrical or mechanical ignition failures step-by-step:")
        q1 = st.radio("Step 1: Does the instrument cluster light up when turning the key ON?", ["Select...", "Yes - Full Power", "No - Complete Blackout"])
        if q1 == "No - Complete Blackout":
            st.warning("⚡ **Diagnosis:** Dead battery, blown main fuse, or detached terminal ring.")
        elif q1 == "Yes - Full Power":
            q2 = st.radio("Step 2: Press the start button. What do you hear?", ["Select...", "Nothing / Single Click", "Engine cranks normally but won't catch"])
            if q2 == "Nothing / Single Click":
                st.warning("🛑 **Diagnosis:** Engine kill switch is ON, bike is in gear with the kickstand down, or starter solenoid is fried.")
            elif q2 == "Engine cranks normally but won't catch":
                q3 = st.radio("Step 3: Check delivery lines. Is there fuel in the tank?", ["Select...", "Yes", "No"])
                if q3 == "No":
                    st.success("⛽ **Diagnosis:** Add gasoline to the fuel chamber reservoir.")
                elif q3 == "Yes":
                    st.info("🔧 **Diagnosis:** Spark plug ignition tracking or clogged injectors are likely causing the engine failure.")

    st.divider()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["text"])

    if user_prompt := st.chat_input("Ask a diagnostic question..."):
        with st.chat_message("user"):
            st.write(user_prompt)
        st.session_state.messages.append({"role": "user", "text": user_prompt})

        with st.chat_message("assistant"):
            with st.spinner("Processing framework diagnostic pipelines..."):
                try:
                    if uploaded_file:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_name = f"bike_{active_bike['id']}_{timestamp}.png"
                        local_path = os.path.join(IMAGE_DIR, file_name)
                        img = Image.open(uploaded_file)
                        img.save(local_path)
                        log_visual_inspection(active_bike['id'], local_path, active_bike['current_mileage'], inspection_label)
                        response = st.session_state.chat.send_message([user_prompt, img])
                    else:
                        response = st.session_state.chat.send_message(user_prompt)
                    
                    if hasattr(response, 'text') and response.text:
                        st.write(response.text)
                        st.session_state.messages.append({"role": "assistant", "text": response.text})
                    else:
                        st.write("I've evaluated your vehicle manual data mapping profile parameters.")
                        st.session_state.messages.append({"role": "assistant", "text": "Processed details."})

                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        error_msg = "⚠️ Rate limit hit. Please wait 15–20 seconds before resending your message!"
                    else:
                        error_msg = f"⚠️ Gemini experienced an error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "text": error_msg})

with tab_service:
    st.subheader("📋 Maintenance Service Book")
    history = get_service_history(active_bike['id'])
    if not history:
        st.info("No service events logged yet.")
    else:
        for record in history:
            with st.container(border=True):
                st.markdown(f"### **{record['service_type']}**")
                st.markdown(f"📍 ` {record['mileage']} km ` | 💰 ` ${record['cost']:.2f} `")
                if record['notes']:
                    st.caption(f"Notes: {record['notes']}")

with tab_analytics:
    st.subheader("📊 Fleet Cost Analytics")
    fuel_data = get_fuel_history(active_bike['id'])
    if not fuel_data or len(fuel_data) < 2:
        st.info("Log at least two refueling entries to compile graphing diagnostics.")
        total_fuel_cost = sum([f['cost'] for f in fuel_data]) if fuel_data else 0.0
    else:
        try:
            df = pd.DataFrame(fuel_data)
            df['distance'] = df['mileage'].diff()
            df['km_per_liter'] = df['distance'] / df['liters']
            df_charts = df.dropna(subset=['km_per_liter'])
            st.markdown("**Fuel Efficiency History ($km/L$)**")
            st.line_chart(df_charts.set_index('mileage')['km_per_liter'])
            total_fuel_cost = df['cost'].sum()
        except Exception:
            total_fuel_cost = 0.0

    total_service_cost = sum([r['cost'] for r in history])
    
    c1, c2 = st.columns(2)
    c1.metric(label="Total Fuel Expense", value=f"${total_fuel_cost:.2f}")
    c2.metric(label="Total Maintenance Cost", value=f"${total_service_cost:.2f}")
    
    st.markdown("**Expense Distribution Structure**")
    expense_df = pd.DataFrame({"Category": ["Fuel Expenses", "Maintenance"], "Total Expended ($)": [total_fuel_cost, total_service_cost]})
    st.bar_chart(expense_df.set_index("Category"))

    st.divider()

    st.subheader("📷 Component Wear Gallery")
    gallery_photos = get_visual_inspections(active_bike['id'])
    if not gallery_photos:
        st.info("No diagnostic photo assets uploaded yet.")
    else:
        for photo in gallery_photos:
            if os.path.exists(photo['file_path']):
                with st.container(border=True):
                    st.image(photo['file_path'], caption=f"{photo['label']} ({photo['mileage']} km)", use_container_width=True)