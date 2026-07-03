import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
from datetime import datetime

# =====================================================================
# I. FIREBASE INITIALIZATION
# =====================================================================
if not firebase_admin._apps:
    if "FIREBASE_CREDENTIALS" in st.secrets:
        cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
    else:
        with open("firebase_key.json", "r") as f:
            cred_dict = json.load(f)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://test-mode-a344c-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# =====================================================================
# II. DATA FUNCTIONS
# =====================================================================
def get_active_vehicle(user_id):
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    if not vehicles: return None
    for vid, vdata in vehicles.items():
        if vdata.get('is_active'):
            vdata['id'] = vid
            return vdata
    return None

def add_new_vehicle(user_id, make, model, current_mileage):
    ref = db.reference(f'users/{user_id}/vehicles').push()
    ref.set({'make': make, 'model': model, 'current_mileage': current_mileage, 'is_active': True})

def log_event(vehicle_id, event_type, details):
    # This stores logs in a separate path for history
    ref = db.reference(f'logs/{vehicle_id}/{event_type}').push()
    ref.set({'details': details, 'timestamp': datetime.now().isoformat()})

# =====================================================================
# III. UI INTERFACE
# =====================================================================
st.set_page_config(page_title="MotoMechanic OS", layout="wide")
st.title("🏍️ MotoMechanic Enterprise OS")

user_id = st.sidebar.selectbox("Operator:", ["Rider_Alpha", "Rider_Beta"])

# Sidebar: Add New Vehicle
with st.sidebar.expander("➕ Add New Vehicle"):
    new_make = st.text_input("Make")
    new_model = st.text_input("Model")
    new_odo = st.number_input("Starting Mileage", value=0)
    if st.button("Register Bike"):
        add_new_vehicle(user_id, new_make, new_model, new_odo)
        st.rerun()

# Main Dashboard
active_bike = get_active_vehicle(user_id)

if active_bike:
    st.subheader(f"Dashboard: {active_bike['make']} {active_bike['model']}")
    st.metric("Current Mileage", f"{active_bike.get('current_mileage', 0)} KM")
    
    # Feature: Fuel Logger
    with st.expander("⛽ Log Refueling"):
        liters = st.number_input("Liters", 0.0)
        cost = st.number_input("Cost", 0.0)
        if st.button("Log Fuel"):
            log_event(active_bike['id'], "fuel", {"liters": liters, "cost": cost})
            st.success("Fuel event saved to cloud!")
            
    # Feature: Service Log
    with st.expander("🔧 Log Service"):
        service_desc = st.text_input("Work Done")
        if st.button("Log Service"):
            log_event(active_bike['id'], "service", {"work": service_desc})
            st.success("Service event saved to cloud!")
else:
    st.info("No active vehicle found. Use the sidebar to register your first bike.")
