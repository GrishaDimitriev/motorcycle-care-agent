import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
import os
from datetime import datetime
from google import genai
from google.genai import types
from googlesearch import search
from PIL import Image

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
# II. DATA FUNCTIONS (FIREBASE VERSION)
# =====================================================================
def get_active_vehicle(user_id):
    # Firebase path: users -> user_id -> vehicles
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    if not vehicles: return None
    for vid, vdata in vehicles.items():
        if vdata.get('is_active'):
            vdata['id'] = vid
            return vdata
    return None

def log_fuel_event(vehicle_id, mileage, liters, cost):
    ref = db.reference(f'fuel_logs/{vehicle_id}')
    ref.push({
        'mileage': mileage,
        'liters': liters,
        'cost': cost,
        'date': datetime.now().isoformat()
    })
    db.reference(f'vehicles/{vehicle_id}').update({'current_mileage': mileage})

def add_new_vehicle(user_id, make, model, current_mileage):
    # This creates a unique reference for the new bike
    new_bike_ref = db.reference(f'users/{user_id}/vehicles').push()
    new_bike_ref.set({
        'make': make,
        'model': model,
        'current_mileage': current_mileage,
        'is_active': True # New bikes automatically become the 'active' one
    })

with st.sidebar.expander("➕ Add New Vehicle"):
    new_make = st.text_input("Make")
    new_model = st.text_input("Model")
    new_odo = st.number_input("Starting Mileage", value=0)
    if st.button("Register Bike"):
        add_new_vehicle(user_id, new_make, new_model, new_odo)
        st.success("Bike added! Refreshing...")
        st.rerun()

# =====================================================================
# III. UI & MAIN INTERFACE
# =====================================================================
st.set_page_config(page_title="MotoMechanic OS", layout="wide")

st.markdown("""
    <link rel="manifest" href="/manifest.json">
    <style>
        body { background-color: #F8F9FA; font-family: 'Inter', sans-serif; }
        .telemetry-badge { background: #F1F3F4; padding: 10px; border-left: 4px solid #1A73E8; border-radius: 4px; margin: 5px 0; }
    </style>
""", unsafe_allow_html=True)

st.title("🏍️ MotoMechanic Enterprise OS")
user_id = st.sidebar.selectbox("Operator:", ["Rider_Alpha", "Rider_Beta"])

active_bike = get_active_vehicle(user_id)

if active_bike:
    st.sidebar.markdown(f"### Active: {active_bike['make']} {active_bike['model']}")
    st.sidebar.markdown(f"<div class='telemetry-badge'>ODO: {active_bike.get('current_mileage', 0)} KM</div>", unsafe_allow_html=True)

    with st.expander("⛽ Log Refueling"):
        m = st.number_input("Mileage", value=active_bike.get('current_mileage', 0))
        l = st.number_input("Liters", value=10.0)
        c = st.number_input("Cost", value=20.0)
        if st.button("Save"):
            log_fuel_event(active_bike['id'], m, l, c)
            st.success("Synced to Cloud!")
            st.rerun()
else:
    st.info("No active vehicle found. Please initialize your profile in Firebase.")
