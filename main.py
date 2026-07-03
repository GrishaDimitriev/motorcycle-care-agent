import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from googlesearch import search  # Import the search package

# Load the API key from your hidden .env file
load_dotenv()

# 1. Initialize the Gemini Client
client = genai.Client()

# 2. Define the Motorcycle Profile structure
class BikeProfile(BaseModel):
    make: str = Field(description="Manufacturer, e.g., Honda, Yamaha")
    model: str = Field(description="Model name, e.g., MT-07, CB500X")
    year: int
    current_mileage: int = Field(description="Current odometer reading in km")
    last_oil_change_mileage: int = Field(description="Mileage at last oil change")

# Define your bike's exact stats
MY_BIKE = BikeProfile(
    make="Yamaha",
    model="MT-07",
    year=2022,
    current_mileage=14200,
    last_oil_change_mileage=10000
)

# 3. Tool 1: The maintenance tracker tool
def check_my_bike_service_status() -> str:
    """Checks the maintenance and service schedule logs for the rider's active motorcycle profile."""
    mileage_since_oil = MY_BIKE.current_mileage - MY_BIKE.last_oil_change_mileage
    km_remaining = 5000 - mileage_since_oil
    
    if mileage_since_oil >= 5000:
        return f"System Log: The {MY_BIKE.make} is overdue for an oil change by {abs(km_remaining)} km."
    return f"System Log: The oil is currently fine. {km_remaining} km left until the next change."

# 4. Tool 2: Custom Python Web Search tool
def search_web_for_motorcycle_specs(query: str) -> str:
    """Searches Google for mechanical specifications, fluid capacities, or torque specs for motorcycles."""
    print(f"\n[Agent Tool] Running Google Search for: '{query}'...")
    try:
        results = []
        # Fetch the top 3 URLs from Google
        for url in search(query, num_results=3):
            results.append(url)
        return f"Search successful. Found relevant specs at these URLs: {', '.join(results)}. Please summarize this fact for the user."
    except Exception as e:
        return f"Search failed due to an error: {str(e)}"

# 5. Set up System Instructions
system_instruction = f"""
You are 'MotoMechanic AI', an expert motorcycle technician. 
You are talking to a rider who owns a {MY_BIKE.year} {MY_BIKE.make} {MY_BIKE.model}.

You have two custom tools available:
1. `check_my_bike_service_status`: Use this to look at the user's mileage logs.
2. `search_web_for_motorcycle_specs`: Use this if the user asks for top speed, parts specs, fluid capacities, or torque details that require looking up online information.

Be highly accurate with mechanical data. 
Safety Rule: Always tell the user to check their factory service manual for structural engine or brake repairs. Do not guess torque settings.
"""

# 6. Initialize the Chat Session with BOTH Python tools
chat = client.chats.create(
    model='gemini-2.5-flash',
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        # Both are regular functions now, completely avoiding the conflict!
        tools=[check_my_bike_service_status, search_web_for_motorcycle_specs], 
        temperature=0.7
    )
)

print("==================================================")
print(f" MotoMechanic AI (Multi-Tool Active) for {MY_BIKE.make} {MY_BIKE.model}!")
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
        
    print("Mechanic is looking up details...")
    
    response = chat.send_message(user_input)
    print(f"\nMotoMechanic: {response.text}\n")