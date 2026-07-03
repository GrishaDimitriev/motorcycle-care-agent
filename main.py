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
        # Load from Cloud Secrets
        cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
    else:
        # Load from local file for development
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
    new_bike_ref = db.reference(f'users/{user_id}/vehicles').push()
    new_bike_ref.set({
        'make': make,
        'model': model,
        'current_mileage': current_mileage,
        'is_active': True
    })

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
    
    # FIXED: The function is only called inside this button block
    if st.button("Register Bike"):
        if new_make and new_model:
            add_new_vehicle(user_id, new_make, new_model, new_odo)
            st.success("Bike registered!")
            st.rerun()
        else:
            st.error("Please enter make and model.")

# Main Dashboard
active_bike = get_active_vehicle(user_id)

if active_bike:
    st.subheader(f"Dashboard: {active_bike['make']} {active_bike['model']}")
    st.metric("Current Mileage", f"{active_bike.get('current_mileage', 0)} KM")
else:
    st.info("No active vehicle found. Use the sidebar to register your first bike.")
