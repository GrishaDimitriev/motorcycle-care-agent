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
# I. PRODUCTION CORE DATABASE ENGINE
# =====================================================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'Default_User',
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
    if 'user_id' not in columns:
        cursor.execute("ALTER TABLE vehicles ADD COLUMN user_id TEXT DEFAULT 'Default_User'")
    if 'color' not in columns:
        cursor.execute("ALTER TABLE vehicles ADD COLUMN color TEXT DEFAULT 'Black'")
    conn.commit()

    cursor.execute("UPDATE vehicles SET user_id = 'Rider_Alpha' WHERE user_id = 'Default_User'")
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

    cursor.execute("PRAGMA table_info(rag_stores)")
    rag_columns = [col[1] for col in cursor.fetchall()]
    if rag_columns and 'vehicle_id' not in rag_columns:
        cursor.execute("DROP TABLE rag_stores")
        conn.commit()

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
    conn.commit()
    conn.close()

init_db()

# --- DATA ACTIONS ---
def get_active_vehicle_for_user(user_id: str) -> dict:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles WHERE user_id = ? AND is_active = 1 LIMIT 1", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT * FROM vehicles WHERE user_id = ? LIMIT 1", (user_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE vehicles SET is_active = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("UPDATE vehicles SET is_active = 1 WHERE id = ?", (row['id'],))
            conn.commit()
            cursor.execute("SELECT * FROM vehicles WHERE id = ?", (row['id'],))
            row = cursor.fetchone()
    conn.close()
    
    if not row:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE vehicles SET is_active = 0 WHERE user_id = ?", (user_id,))
        if user_id == "Rider_Beta":
            cursor.execute("INSERT INTO vehicles (user_id, make, model, year, current_mileage, last_oil_change_mileage, color, is_active) VALUES ('Rider_Beta', 'Honda', 'CB500X', 2021, 15000, 12000, 'Red', 1)")
        elif user_id == "Guest_Mechanic":
            cursor.execute("INSERT INTO vehicles (user_id, make, model, year, current_mileage, last_oil_change_mileage, color, is_active) VALUES ('Guest_Mechanic', 'Yamaha', 'YZF-R6', 2018, 22000, 20000, 'Blue', 1)")
        else:
            cursor.execute("INSERT INTO vehicles (user_id, make, model, year, current_mileage, last_oil_change_mileage, color, is_active) VALUES ('Rider_Alpha', 'Kawasaki', 'Ninja 250R', 2008, 45000, 40000, 'Black', 1)")
        conn.commit()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vehicles WHERE user_id = ? AND is_active = 1 LIMIT 1", (user_id,))
        conn.row_factory = sqlite3.Row
        row = cursor.fetchone()
        conn.close()
    return dict(row)

def get_vehicles_by_user(user_id: str) -> list:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_active_vehicle_for_user(user_id: str, vehicle_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE vehicles SET is_active = 0 WHERE user_id = ?", (user_id,))
    cursor.execute("UPDATE vehicles SET is_active = 1 WHERE user_id = ? AND id = ?", (user_id, vehicle_id))
    conn.commit()
    conn.close()

def add_new_vehicle_for_user(user_id: str, make: str, model: str, year: int, mileage: int, last_oil: int, color: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE vehicles SET is_active = 0 WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO vehicles (user_id, make, model, year, current_mileage, last_oil_change_mileage, color, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)", (user_id, make, model, year, mileage, last_oil, color))
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
    conn.row_factory = sqlite3.Row
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

def search_web_for_motorcycle_specs(query: str) -> str:
    """Searches Google for mechanical specifications, fluid capacities, or torque specs for motorcycles."""
    try:
        results = []
        for url in search(query, num_results=3):
            results.append(url)
        return f"Search successful. Found specs at these URLs: {', '.join(results)}."
    except Exception as e:
        return f"Search failed due to an error: {str(e)}"


# =====================================================================
# II. STREAMLIT GLOBAL GOOGLE MATERIAL DESIGN INJECTION (CSS OVERRIDES)
# =====================================================================
# Clean, crisp layout structure inspired by standard desktop workspace templates
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* Global Reset to Clean Google Light Theme Canvas */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            background-color: #F8F9FA !important;
            color: #202124 !important;
        }
        
        /* Sidebar container layout overrides - Soft Clean Gray */
        [data-testid="stSidebar"], [data-testid="stSidebarUserContent"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E8EAED !important;
        }
        
        /* Force high contrast dark charcoal text inside white sidebar elements */
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
            color: #3C4043 !important;
            font-weight: 500 !important;
        }
        
        h1, h2, h3, h4, h5, h6 {
            font-weight: 600 !important;
            letter-spacing: -0.01em !important;
            color: #202124 !important;
        }
        
        /* Modern Material Design Elevation Cards replacing dark boxes */
        div[data-testid="stVerticalBlockBorderContainer"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E8EAED !important;
            border-radius: 8px !important;
            padding: 24px !important;
            box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15) !important;
        }
        
        /* Google Telemetry Badge */
        .telemetry-badge {
            background-color: #F1F3F4 !important;
            border: 1px solid #E8EAED !important;
            border-left: 4px solid #1A73E8 !important;
            padding: 12px 16px;
            border-radius: 6px;
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            font-weight: 600 !important;
            color: #3C4043 !important;
            margin: 8px 0;
        }
        
        /* Navigation Tabs formatting logic layout updates - Clean Google Style */
        button[data-baseweb="tab"] {
            font-weight: 500 !important;
            font-size: 14px !important;
            color: #5F6368 !important;
            border-bottom-width: 3px !important;
            background-color: transparent !important;
            padding: 12px 16px !important;
        }
        
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #1A73E8 !important;
            border-bottom-color: #1A73E8 !important;
        }
        
        /* Clean Google Blue Primary Action Buttons */
        div.stButton > button {
            background: #1A73E8 !important;
            color: #FFFFFF !important;
            font-weight: 500 !important;
            border-radius: 4px !important;
            border: none !important;
            padding: 8px 24px !important;
            box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3) !important;
            transition: background-color 0.2s, box-shadow 0.2s !important;
        }
        div.stButton > button:hover {
            background: #1557B0 !important;
            box-shadow: 0 1px 3px 0 rgba(60,64,67,0.3), 0 4px 8px 3px rgba(60,64,67,0.15) !important;
        }
        
        /* Target dropdown/number inputs styling compatibility layer */
        div[data-baseweb="select"] > div, div[data-testid="stNumberInput"] input {
            background-color: #FFFFFF !important;
            color: #202124 !important;
            border: 1px solid #DADCE0 !important;
            border-radius: 4px !important;
        }
        
        /* Text input fields background fix for consistency */
        input, select, textarea {
            color: #202124 !important;
        }
    </style>
""", unsafe_allow_html=True)


# =====================================================================
# III. STREAMLIT SIDEBAR COMPONENT PANEL
# =====================================================================
st.sidebar.markdown("<h3 style='color: #1A73E8; margin-bottom:0;'>🔐 Account Profile</h3>", unsafe_allow_html=True)
current_user = st.sidebar.selectbox("Operator ID Switcher:", ["Rider_Alpha", "Rider_Beta", "Guest_Mechanic"], label_visibility="collapsed")

active_bike = get_active_vehicle_for_user(current_user)
all_bikes = get_vehicles_by_user(current_user)

st.sidebar.divider()
st.sidebar.markdown("### 🏢 Fleet Sub-Garage")

bike_options = {f"{b['year']} {b['make']} {b['model']}": b['id'] for b in all_bikes}
current_index = 0
active_bike_string = f"{active_bike['year']} {active_bike['make']} {active_bike['model']}"
if active_bike_string in bike_options:
    current_index = list(bike_options.keys()).index(active_bike_string)
        
selected_bike_name = st.sidebar.selectbox("Select Target Vehicle:", list(bike_options.keys()), index=current_index)

if bike_options[selected_bike_name] != active_bike['id']:
    set_active_vehicle_for_user(current_user, bike_options[selected_bike_name])
    if "chat" in st.session_state:
        del st.session_state.chat
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown(f"### 🏍️ Active Unit: **{active_bike['make']} {active_bike['model']}**")

# High-visibility Material Badges
st.sidebar.markdown(f"<div class='telemetry-badge'>Color Specification: {active_bike.get('color', 'Black').title()}</div>", unsafe_allow_html=True)
st.sidebar.markdown(f"<div class='telemetry-badge'>Odometer Track: {active_bike['current_mileage']} km</div>", unsafe_allow_html=True)
st.sidebar.markdown(f"<div class='telemetry-badge'>Lubricant Interval Age: {active_bike['current_mileage'] - active_bike['last_oil_change_mileage']} km</div>", unsafe_allow_html=True)

new_mileage = st.sidebar.number_input("Log kilometers ridden:", min_value=active_bike['current_mileage'], value=active_bike['current_mileage'])
if st.sidebar.button("Update Telemetry"):
    update_mileage_in_db(active_bike['id'], new_mileage)
    st.sidebar.success("Odometer sync complete!")
    st.rerun()

st.sidebar.divider()

st.sidebar.subheader("📖 Manual RAG Index Core")
expected_manual_path = f"manuals/{active_bike['id']}/service_manual.pdf"
active_rag_store = get_indexed_rag_store_for_vehicle(active_bike['id'])

if not active_rag_store:
    if os.path.exists(expected_manual_path):
        st.sidebar.warning("Manual detected but unindexed.")
        if st.sidebar.button("⚡ Index Profile Manual"):
            with st.sidebar.spinner("Uploading separate vehicle manual context..."):
                try:
                    store = client.file_search_stores.create(
                        config={"display_name": f"manual-id-{active_bike['id']}", "embedding_model": "models/gemini-embedding-2"}
                    )
                    operation = client.file_search_stores.upload_to_file_search_store(
                        file_search_store_name=store.name, file=expected_manual_path, config={"display_name": f"Manual {active_bike['id']}"}
                    )
                    while not operation.done:
                        time.sleep(3)
                        operation = client.operations.get(operation=operation)
                        
                    log_indexed_rag_store_for_vehicle(active_bike['id'], store.name, "service_manual.pdf")
                    st.sidebar.success("Manual integrated!")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Ingestion crashed: {str(e)}")
    else:
        st.sidebar.info(f"Place a text PDF inside `{expected_manual_path}` to map custom data grounding matrices.")
else:
    st.sidebar.success(f"🟢 Active Index: Loaded (ID {active_bike['id']})")

st.sidebar.divider()

with st.sidebar.expander("⛽ Log Refueling Invoice"):
    fuel_mileage = st.number_input("Station Odometer Reading (km):", min_value=0, value=active_bike['current_mileage'])
    fuel_liters = st.number_input("Liters Fueled:", min_value=0.0, value=10.0, step=1.0)
    fuel_cost = st.number_input("Total Bill Cost ($):", min_value=0.0, value=20.0, step=1.0)
    if st.button("Save Fuel Log"):
        log_fuel_event(active_bike['id'], fuel_mileage, fuel_liters, fuel_cost)
        st.sidebar.success("Fuel log entry committed!")
        st.rerun()

with st.sidebar.expander("🛠️ Record Shop Maintenance"):
    service_type = st.selectbox("Job Selection:", ["Routine Oil Change", "Brake Pad Flush", "Chain Service", "Tire Replacement", "General Inspection", "Custom Repair"])
    log_mileage = st.number_input("Performed Mileage (km):", min_value=0, value=active_bike['current_mileage'])
    log_cost = st.number_input("Total Operations Cost ($):", min_value=0.0, value=0.0, step=5.0)
    log_notes = st.text_area("Mechanic Notes Analysis:")
    if st.button("Commit Service Event"):
        log_service_event(active_bike['id'], service_type, log_mileage, log_cost, log_notes)
        st.sidebar.success("Service event appended!")
        st.rerun()

with st.sidebar.expander("📝 Modify Bike Profile Details"):
    edit_make = st.text_input("Make:", value=active_bike['make'])
    edit_model = st.text_input("Model:", value=active_bike['model'])
    edit_year = st.number_input("Configuration Year:", min_value=1900, max_value=2028, value=active_bike['year'])
    edit_color = st.text_input("Color Spec:", value=active_bike.get('color', 'Black'))
    if st.button("Save Adjustments"):
        update_vehicle_details(active_bike['id'], edit_make, edit_model, edit_year, edit_color)
        st.success("Target profile updated!")
        if "chat" in st.session_state:
            del st.session_state.chat
        st.rerun()

with st.sidebar.expander("➕ Park New Bike Entity"):
    new_make = st.text_input("Manufacturer:")
    new_model = st.text_input("Model:")
    new_year = st.number_input("Year Tag:", min_value=1900, max_value=2028, value=2024)
    new_color = st.text_input("Exterior Finish:", value="Black")
    new_odo = st.number_input("Odometer Baseline:", min_value=0, value=5000)
    new_oil = st.number_input("Oil Service Baseline:", min_value=0, value=4000)
    if st.button("Register to Garage"):
        if new_make and new_model:
            add_new_vehicle_for_user(current_user, new_make, new_model, new_year, new_odo, new_oil, new_color)
            st.success("Vehicle entity mapped!")
            if "chat" in st.session_state:
                del st.session_state.chat
            st.rerun()

st.sidebar.divider()
st.sidebar.subheader("📷 Visual Component Input")
uploaded_file = st.sidebar.file_uploader("Upload component asset:", type=["jpg", "jpeg", "png"])
inspection_label = st.sidebar.text_input("Asset Label:", value="Diagnostic Asset")

if uploaded_file:
    st.sidebar.image(uploaded_file, caption="Staged Inspection Asset", use_container_width=True)


# =====================================================================
# IV. CORE CORE AI SESSION PIPELINES
# =====================================================================
if "chat" not in st.session_state or "current_bike_id" not in st.session_state or st.session_state.current_bike_id != active_bike['id']:
    st.session_state.current_bike_id = active_bike['id']
    
    system_instruction = f"""You are 'MotoMechanic AI', a premium diagnostic suite engine system assistant. 
    You are evaluating maintenance data metrics for User Account Profile Code '{current_user}' managing a {active_bike.get('color', 'Black')} {active_bike['year']} {active_bike['make']} {active_bike['model']}.
    Use search_web_for_motorcycle_specs if they seek matching parts item links. 
    Safety Boundary Parameter: Always instruct the operator to cross reference official factory specs tables."""
    
    available_tools = [search_web_for_motorcycle_specs]
    if active_rag_store:
        file_search_tool = types.Tool(file_search=types.FileSearch(file_search_retrieval_resources=[types.FileSearchRetrievalResource(file_search_store_name=active_rag_store)]))
        available_tools.append(file_search_tool)
    
    st.session_state.chat = client.chats.create(
        model='gemini-2.5-flash',
        config=types.GenerateContentConfig(system_instruction=system_instruction, tools=available_tools, temperature=0.7)
    )

if "messages" not in st.session_state:
    st.session_state.messages = []


# =====================================================================
# V. MAIN RENDER LAYER (MODERN TABS ARCHITECTURE)
# =====================================================================
st.markdown(f"<h1 style='margin-bottom:0;'>🏍️ Fleet Management <span style='color:#1A73E8;'>Console</span></h1>", unsafe_allow_html=True)
st.caption(f"Operator Node Context: `{current_user}` | Core Matrix Focus: {active_bike['year']} {active_bike['make']} {active_bike['model']}")

tab_chat, tab_service, tab_analytics, tab_predictive, tab_marketplace = st.tabs([
    "💬 Core Agent Terminal", "📋 Service Logs Book", "📊 Fleet Analytics charts", "🔮 ML Wear Predictions", "🛒 Parts Sourcing System"
])

# --- TAB 1: CORE AGENT CONTROLS ---
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

    if user_prompt := st.chat_input("Input hardware service query..."):
        with st.chat_message("user"):
            st.write(user_prompt)
        st.session_state.messages.append({"role": "user", "text": user_prompt})

        with st.chat_message("assistant"):
            with st.spinner("Processing framework analytical vector streams..."):
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
                    
                    st.write(response.text)
                    st.session_state.messages.append({"role": "assistant", "text": response.text})
                except Exception as e:
                    st.error(f"Ecosystem pipeline exception: {str(e)}")

# --- TAB 2: TIMELINE HISTORY LOGS ---
with tab_service:
    st.subheader("📋 Relational Service Timeline Data")
    history = get_service_history(active_bike['id'])
    if not history:
        st.info("No recorded maintenance tracking entries mapped for this vehicle entity profile node.")
    else:
        for record in history:
            with st.container(border=True):
                st.markdown(f"### **{record['service_type']}**")
                st.markdown(f"📍 Odometer Focus: `{record['mileage']} km` | 💸 Invoiced Cost: `${record['cost']:.2f}`")
                st.caption(f"System Log Timestamp: {record['date_logged']}")
                if record['notes']:
                    st.info(f"**Operator/Mechanic Diagnostic Notes:** {record['notes']}")

# --- TAB 3: CONSUMPTION DIAGNOSTICS CHARTS ---
with tab_analytics:
    st.subheader("📊 Fleet Cost Analytics Invoicing Matrix")
    fuel_data = get_fuel_history(active_bike['id'])
    if not fuel_data or len(fuel_data) < 2:
        st.info("Log at least two refueling invoice records to extract dynamic graphing vectors.")
        total_fuel_cost = sum([f['cost'] for f in fuel_data]) if fuel_data else 0.0
    else:
        try:
            df = pd.DataFrame(fuel_data)
            df['distance'] = df['mileage'].diff()
            df['km_per_liter'] = df['distance'] / df['liters']
            df_charts = df.dropna(subset=['km_per_liter'])
            st.markdown("**Fuel Efficiency History Graph Tracking ($km/L$)**")
            st.line_chart(df_charts.set_index('mileage')['km_per_liter'])
            total_fuel_cost = df['cost'].sum()
        except Exception:
            total_fuel_cost = 0.0

    total_service_cost = sum([r['cost'] for r in history])
    c1, c2 = st.columns(2)
    c1.metric("Aggregated Refueling Invoices", f"${total_fuel_cost:.2f}")
    c2.metric("Aggregated Service Invoices", f"${total_service_cost:.2f}")
    
    st.markdown("**Operational Budget Allocation Distribution Structure**")
    expense_df = pd.DataFrame({"Category": ["Refueling Expense", "Maintenance Operation"], "Expended Capital ($)": [total_fuel_cost, total_service_cost]})
    st.bar_chart(expense_df.set_index("Category"))

# --- TAB 4: COMPONENT WEAR ML ALERTS ---
with tab_predictive:
    st.subheader("🔮 Predictive Machine Learning Wear Forecasts")
    st.write("Tracking hardware consumption profiles relative to shelf-life degradation benchmarks:")
    
    mileage_since_oil = active_bike["current_mileage"] - active_bike["last_oil_change_mileage"]
    oil_health_factor = max(0, int(((5000 - mileage_since_oil) / 5000) * 100))
    
    st.markdown(f"### **Engine Lubricant Shelf Life Remaining: `{oil_health_factor}%`**")
    st.progress(oil_health_factor / 100)
    
    if oil_health_factor > 50:
        st.success("🟢 Diagnostic Status: Matrix stable. Lubricity index optimal.")
    elif oil_health_factor > 15:
        st.warning("🟡 Diagnostic Status: Viscosity degradation warning. Schedule filter swaps within 750km.")
    else:
        st.error("🔴 Critical Boundary Exception: Fluid failure limits crossed! Service immediately.")
        
    st.divider()
    st.markdown("### **Structural Predictive Component Lifecycle Tracking Matrix**")
    
    current_odo = active_bike["current_mileage"]
    prediction_matrix = [
        {"Component Target": "Drive Chain Tension/Slack Check", "Last Event": f"{current_odo - (current_odo % 1000)} km", "Predicted Next Service": f"{current_odo - (current_odo % 1000) + 1000} km", "Risk Level Alert": "Low"},
        {"Component Target": "Front/Rear Brake Pad Thickness", "Last Event": f"{current_odo - (current_odo % 15000)} km", "Predicted Next Service": f"{current_odo - (current_odo % 15000) + 15000} km", "Risk Level Alert": "Medium"},
        {"Component Target": "Spark Plug Ignition Coils Replacement", "Last Event": f"{current_odo - (current_odo % 12000)} km", "Predicted Next Service": f"{current_odo - (current_odo % 12000) + 12000} km", "Risk Level Alert": "Low"},
        {"Component Target": "Valve Clearance Profile Calibration", "Last Event": f"{current_odo - (current_odo % 24000)} km", "Predicted Next Service": f"{current_odo - (current_odo % 24000) + 24000} km", "Risk Level Alert": "High Threshold"}
    ]
    st.table(pd.DataFrame(prediction_matrix))

# --- TAB 5: PARTS INTEGRATION MARKETPLACE ---
with tab_marketplace:
    st.subheader("🛒 Automated Component Marketplace Sourcing Channel")
    st.write("Cross-referencing supplier logs matching active engine configurations:")
    
    selected_target_part = st.selectbox(
        "Sourcing Component Requirement Asset:", 
        ["High-Performance 10W-40 Motorcycle Oil", "Front Carbon-Ceramic Brake Pads", "Heavy Duty O-Ring Drive Chain", "OEM Spark Plugs Set", "Premium Track Compound Front Tire"]
    )
    
    search_query = f"buy {active_bike['year']} {active_bike['make']} {active_bike['model']} {selected_target_part}"
    
    if st.button("Search Procurement Channels"):
        with st.spinner("Scraping active inventory distribution matrices..."):
            try:
                results = []
                for url in search(search_query, num_results=4):
                    results.append(url)
                
                st.success("Marketplace engine returned active storefront matching references:")
                for index, link in enumerate(results, start=1):
                    with st.container(border=True):
                        st.markdown(f"📦 **Supplier Channel Pipeline Vendor #{index}**")
                        st.caption(f"Verified item match index path for {active_bike['make']} {active_bike['model']}")
                        st.markdown(f"[Proceed to Procurement Storefront Link]({link})")
            except Exception as e:
                st.error(f"Marketplace sourcing lookup failure: {str(e)}")

    st.divider()
    st.subheader("📷 Component Wear Visual Image Log Gallery")
    gallery_photos = get_visual_inspections(active_bike['id'])
    if not gallery_photos:
        st.info("No photo wear logs archived yet.")
    else:
        for photo in gallery_photos:
            if os.path.exists(photo['file_path']):
                with st.container(border=True):
                    st.image(photo['file_path'], caption=f"{photo['label']} ({photo['mileage']} km)", use_container_width=True)