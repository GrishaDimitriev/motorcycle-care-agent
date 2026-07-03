import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from googlesearch import search

# Load the API key from your hidden .env file
load_dotenv()

# 1. Initialize the Gemini Client
client = genai.Client()

# Path to our local data storage file
PROFILE_FILE = "bike_profile.json"

# Helper Function: Load the bike profile from the JSON file
def load_bike_profile() -> dict:
    with open(PROFILE_FILE, "r") as f:
        return json.load(f)

# Helper Function: Save the updated bike profile back to the JSON file
def save_bike_profile(data: dict):
    with open(PROFILE_FILE, "w") as f:
        json.dump(data, f, indent=4)

# 2. Tool 1: The maintenance tracker tool
def check_my_bike_service_status() -> str:
    """Checks the maintenance and service schedule logs for the rider's active motorcycle profile."""
    bike = load_bike_profile()
    mileage_since_oil = bike["current_mileage"] - bike["last_oil_change_mileage"]
    km_remaining = 5000 - mileage_since_oil
    
    if mileage_since_oil >= 5000:
        return f"System Log: The {bike['make']} is overdue for an oil change by {abs(km_remaining)} km."
    return f"System Log: The oil is currently fine. {km_remaining} km left until the next change."

# 3. Tool 2: The odometer updating tool
def update_bike_odometer(new_mileage: int) -> str:
    """Updates the motorcycle's current odometer mileage record when the rider goes for rides."""
    print(f"\n[Agent Tool] Updating odometer log to: {new_mileage} km...")
    try:
        bike = load_bike_profile()
        
        # Validation to prevent lowering odometer values
        if new_mileage < bike["current_mileage"]:
            return f"Error: The new mileage ({new_mileage} km) cannot be lower than the current mileage ({bike['current_mileage']} km)."
            
        bike["current_mileage"] = new_mileage
        save_bike_profile(bike)
        return f"System Log: Odometer successfully updated to {new_mileage} km."
    except Exception as e:
        return f"Failed to update odometer record due to error: {str(e)}"

# 4. Tool 3: Custom Python Web Search tool
def search_web_for_motorcycle_specs(query: str) -> str:
    """Searches Google for mechanical specifications, fluid capacities, or torque specs for motorcycles."""
    print(f"\n[Agent Tool] Running Google Search for: '{query}'...")
    try:
        results = []
        for url in search(query, num_results=3):
            results.append(url)
        return f"Search successful. Found specs at: {', '.join(results)}. Summarize this fact for the user."
    except Exception as e:
        return f"Search failed: {str(e)}"

# 5. Set up Dynamic System Instructions
bike_data = load_bike_profile()
system_instruction = f"""
You are 'MotoMechanic AI', an expert motorcycle technician. 
You are talking to a rider who owns a {bike_data['year']} {bike_data['make']} {bike_data['model']}.

You have three custom tools available:
1. `check_my_bike_service_status`: Use this to look at the user's current mileage calculations.
2. `update_bike_odometer`: Use this immediately if the user tells you they went for a ride, completed a trip, or want to update their odometer mileage.
3. `search_web_for_motorcycle_specs`: Use this if the user asks for bike details requiring online lookups.

Safety Rule: Always tell the user to check their factory service manual for structural engine or brake repairs.
"""

# 6. Initialize the Chat Session with all three tools
chat = client.chats.create(
    model='gemini-2.5-flash',
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[check_my_bike_service_status, update_bike_odometer, search_web_for_motorcycle_specs], 
        temperature=0.7
    )
)

print("==================================================")
print(f" MotoMechanic AI (Dynamic Memory Active) for {bike_data['make']} {bike_data['model']}!")
print(" Type your questions below. Type 'quit' or 'exit' to stop.")
print("==================================================\n")

# 7. The Continuous Conversation Loop
while True:
    user_input = input("You: ")
    
    if user_input.lower() in ['quit', 'exit']:
        print("\nMechanic checking out. Ride safe!")
        break
        
    if not user_input.strip():
        continue
        
    print("Mechanic is thinking...")
    
    response = chat.send_message(user_input)
    print(f"\nMotoMechanic: {response.text}\n")