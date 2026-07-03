import os
import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from google import genai
from google.genai import types
from googlesearch import search
from PIL import Image
import firebase_admin
from firebase_admin import credentials, db

# --- I. FIREBASE INITIALIZATION ---
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

client = genai.Client()
IMAGE_DIR = "static/inspection_images"
if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR)

# --- II. FIREBASE MAPPED DATA ENGINE ---
def get_active_vehicle_for_user(user_id):
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    if not vehicles: return None
    for vid, vdata in vehicles.items():
        if vdata.get('is_active'):
            vdata['id'] = vid
            return vdata
    return None

def get_vehicles_by_user(user_id):
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    return [{'id': vid, **vdata} for vid, vdata in vehicles.items()] if vehicles else []

def set_active_vehicle_for_user(user_id, vehicle_id):
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    for vid in vehicles: db.reference(f'users/{user_id}/vehicles/{vid}').update({'is_active': 0})
    db.reference(f'users/{user_id}/vehicles/{vehicle_id}').update({'is_active': 1})

def add_new_vehicle_for_user(user_id, make, model, year, mileage, last_oil, color):
    db.reference(f'users/{user_id}/vehicles').push({'user_id': user_id, 'make': make, 'model': model, 'year': year, 'current_mileage': mileage, 'last_oil_change_mileage': last_oil, 'color': color, 'is_active': 1})

def update_mileage_in_db(vehicle_id, new_mileage):
    db.reference(f'users').get() # logic placeholder for user find
    # In practice, track user_id in session state to optimize path
    # Example: db.reference(f'users/{st.session_state.user}/vehicles/{vehicle_id}').update({'current_mileage': new_mileage})

def log_service_event(vehicle_id, service_type, mileage, cost, notes):
    db.reference(f'logs/{vehicle_id}/service').push({'service_type': service_type, 'mileage': mileage, 'cost': cost, 'notes': notes, 'date_logged': datetime.now().isoformat()})

def get_service_history(vehicle_id):
    logs = db.reference(f'logs/{vehicle_id}/service').get()
    return list(logs.values()) if logs else []

def log_fuel_event(vehicle_id, mileage, liters, cost):
    db.reference(f'logs/{vehicle_id}/fuel').push({'mileage': mileage, 'liters': liters, 'cost': cost, 'date_logged': datetime.now().isoformat()})

def get_fuel_history(vehicle_id):
    logs = db.reference(f'logs/{vehicle_id}/fuel').get()
    return list(logs.values()) if logs else []

def log_visual_inspection(vehicle_id, file_path, mileage, label):
    db.reference(f'logs/{vehicle_id}/visual').push({'file_path': file_path, 'mileage': mileage, 'label': label})

def get_visual_inspections(vehicle_id):
    logs = db.reference(f'logs/{vehicle_id}/visual').get()
    return list(logs.values()) if logs else []

def get_indexed_rag_store_for_vehicle(vehicle_id):
    store = db.reference(f'rag_stores/{vehicle_id}').get()
    return store.get('store_name') if store else ""

def log_indexed_rag_store_for_vehicle(vehicle_id, store_name, file_name):
    db.reference(f'rag_stores/{vehicle_id}').set({'store_name': store_name, 'file_name': file_name})

def update_vehicle_details(vehicle_id, make, model, year, color):
    # Update logic (add user_id tracking to session for efficient pathing)
    pass

# --- III. UI, CSS, AND MAIN LOGIC ---
st.set_page_config(page_title="MotoMechanic OS", layout="wide")
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [data-testid="stAppViewContainer"] { font-family: 'Inter', sans-serif !important; background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E8EAED !important; }
    div[data-testid="stVerticalBlockBorderContainer"] { background-color: #FFFFFF !important; border: 1px solid #E8EAED !important; border-radius: 8px !important; box-shadow: 0 1px 2px rgba(60,64,67,0.3) !important; }
    .telemetry-badge { background-color: #F1F3F4 !important; border-left: 4px solid #1A73E8 !important; padding: 12px; border-radius: 6px; font-weight: 600; color: #3C4043; }
</style>
""", unsafe_allow_html=True)

st.title("🏍️ MotoMechanic Enterprise OS")
current_user = st.sidebar.selectbox("Operator ID Switcher:", ["Rider_Alpha", "Rider_Beta", "Guest_Mechanic"])
active_bike = get_active_vehicle_for_user(current_user)

if active_bike:
    tab_chat, tab_service, tab_analytics, tab_predictive, tab_marketplace = st.tabs([
        "💬 Core Agent Terminal", "📋 Service Logs Book", "📊 Fleet Analytics charts", "🔮 ML Wear Predictions", "🛒 Parts Sourcing System"
    ])
    
    with tab_chat:
        # [Insert your original AI/Troubleshooting code here]
        st.write("AI Agent Active")
    with tab_service:
        # [Insert your history code here]
        st.write("History Logs")
    # ... Continue tabs ...
