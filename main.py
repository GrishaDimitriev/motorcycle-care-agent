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
import pandas as pd

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
# II. FIREBASE MAPPED DATA FUNCTIONS
# =====================================================================
def get_active_vehicle_for_user(user_id):
    # Fetch vehicles from Firebase
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    if not vehicles: return None
    for vid, vdata in vehicles.items():
        if vdata.get('is_active'):
            vdata['id'] = vid
            return vdata
    return None

def get_service_history(vehicle_id):
    # Returns history from Firebase
    history = db.reference(f'logs/{vehicle_id}/service').get()
    return list(history.values()) if history else []

def log_service_event(vehicle_id, service_type, mileage, cost, notes):
    db.reference(f'logs/{vehicle_id}/service').push({
        'service_type': service_type, 'mileage': mileage, 
        'cost': cost, 'notes': notes, 'date_logged': datetime.now().isoformat()
    })

def get_fuel_history(vehicle_id):
    history = db.reference(f'logs/{vehicle_id}/fuel').get()
    return list(history.values()) if history else []

# ... (Keep the rest of your original logic here, just ensure they call db.reference()) ...

# =====================================================================
# III. UI & MAIN INTERFACE
# =====================================================================
# (Your original CSS and st.tabs logic remains exactly the same)
# Simply ensure the functions called inside your st.tabs 
# are now the Firebase versions defined above.
