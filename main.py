import os
import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
from googlesearch import search
from PIL import Image
import firebase_admin
from firebase_admin import credentials, db

# --- I. INITIALIZATION ---
load_dotenv()
client = genai.Client()

if not firebase_admin._apps:
    if "FIREBASE_CREDENTIALS" in st.secrets:
        cred_dict = json.loads(st.secrets["FIREBASE_CREDENTIALS"])
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://test-mode-a344c-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# --- II. FIREBASE DATA ENGINE (REPLACES SQLITE) ---
def get_active_vehicle_for_user(user_id: str) -> dict:
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    if vehicles:
        for vid, vdata in vehicles.items():
            if vdata.get('is_active'):
                vdata['id'] = vid
                return vdata
    # Fallback/Auto-register
    new_ref = db.reference(f'users/{user_id}/vehicles').push({
        'make': 'Kawasaki', 'model': 'Ninja 250R', 'year': 2008, 
        'current_mileage': 45000, 'last_oil_change_mileage': 40000, 'color': 'Black', 'is_active': 1
    })
    return {'id': new_ref.key, 'make': 'Kawasaki', 'model': 'Ninja 250R', 'year': 2008, 'current_mileage': 45000, 'last_oil_change_mileage': 40000, 'color': 'Black'}

def get_vehicles_by_user(user_id: str) -> list:
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    return [{'id': vid, **vdata} for vid, vdata in vehicles.items()] if vehicles else []

def set_active_vehicle_for_user(user_id: str, vehicle_id: int):
    vehicles = db.reference(f'users/{user_id}/vehicles').get()
    for vid in vehicles: db.reference(f'users/{user_id}/vehicles/{vid}').update({'is_active': 0})
    db.reference(f'users/{user_id}/vehicles/{vehicle_id}').update({'is_active': 1})

def add_new_vehicle_for_user(user_id, make, model, year, mileage, last_oil, color):
    db.reference(f'users/{user_id}/vehicles').push({
        'make': make, 'model': model, 'year': year, 'current_mileage': mileage, 
        'last_oil_change_mileage': last_oil, 'color': color, 'is_active': 1
    })

def update_mileage_in_db(vehicle_id, new_mileage):
    # This logic identifies the user node to update the specific vehicle
    users = db.reference('users').get()
    for user_id, data in users.items():
        if 'vehicles' in data and vehicle_id in data['vehicles']:
            db.reference(f'users/{user_id}/vehicles/{vehicle_id}').update({'current_mileage': new_mileage})

def log_service_event(vehicle_id, service_type, mileage, cost, notes):
    db.reference(f'logs/{vehicle_id}/service').push({
        'service_type': service_type, 'mileage': mileage, 'cost': cost, 
        'notes': notes, 'date_logged': datetime.now().isoformat()
    })

def get_service_history(vehicle_id) -> list:
    logs = db.reference(f'logs/{vehicle_id}/service').get()
    return list(logs.values()) if logs else []

def log_fuel_event(vehicle_id, mileage, liters, cost):
    db.reference(f'logs/{vehicle_id}/fuel').push({
        'mileage': mileage, 'liters': liters, 'cost': cost, 'date_logged': datetime.now().isoformat()
    })
    update_mileage_in_db(vehicle_id, mileage)

def get_fuel_history(vehicle_id) -> list:
    logs = db.reference(f'logs/{vehicle_id}/fuel').get()
    return list(logs.values()) if logs else []

def log_visual_inspection(vehicle_id, file_path, mileage, label):
    db.reference(f'logs/{vehicle_id}/visual').push({
        'file_path': file_path, 'mileage': mileage, 'label': label
    })

def get_visual_inspections(vehicle_id) -> list:
    logs = db.reference(f'logs/{vehicle_id}/visual').get()
    return list(logs.values()) if logs else []

def get_indexed_rag_store_for_vehicle(vehicle_id):
    store = db.reference(f'rag_stores/{vehicle_id}').get()
    return store.get('store_name') if store else ""

def log_indexed_rag_store_for_vehicle(vehicle_id, store_name, file_name):
    db.reference(f'rag_stores/{vehicle_id}').set({'store_name': store_name, 'file_name': file_name})

# --- III. UI & LOGIC (KEEP YOUR ORIGINAL CSS/TABS) ---
# [Copy/Paste your CSS block from above here]
# [Copy/Paste your Tab layout/Logic from above here]
