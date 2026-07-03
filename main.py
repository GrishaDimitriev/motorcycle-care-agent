import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

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

# 3. Define the tool function the AI can execute
def check_my_bike_service_status() -> str:
    """Checks the maintenance and service schedule logs for the rider's active motorcycle profile."""
    mileage_since_oil = MY_BIKE.current_mileage - MY_BIKE.last_oil_change_mileage
    km_remaining = 5000 - mileage_since_oil
    
    if mileage_since_oil >= 5000:
        return f"System Log: The {MY_BIKE.make} is overdue for an oil change by {abs(km_remaining)} km."
    return f"System Log: The oil is currently fine. {km_remaining} km left until the next change."

# 4. Set up System Instructions telling the AI how to behave
system_instruction = f"""
You are 'MotoMechanic AI', an expert motorcycle technician. 
You are talking to a rider who owns a {MY_BIKE.year} {MY_BIKE.make} {MY_BIKE.model}.

Whenever the user asks you about their maintenance schedule, oil status, or if they need a service, you MUST execute the `check_my_bike_service_status` tool to read their data log before replying. 

Be conversational, helpful, and concise.
Safety Rule: Always tell the user to check their factory service manual for structural engine or brake repairs.
"""

# 5. Initialize a persistent Chat Session with Memory and Tools
# This keeps track of the history automatically across messages
chat = client.chats.create(
    model='gemini-2.5-flash',
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[check_my_bike_service_status], 
        temperature=0.7
    )
)

print("==================================================")
print(f" MotoMechanic AI Active for your {MY_BIKE.make} {MY_BIKE.model}!")
print(" Type your questions below. Type 'quit' or 'exit' to stop.")
print("==================================================\n")

# 6. The Continuous Conversation Loop
while True:
    # Get message from you via the command line
    user_input = input("You: ")
    
    # Break out of the loop if you want to leave
    if user_input.lower() in ['quit', 'exit']:
        print("\nMechanic checking out. Ride safe!")
        break
        
    if not user_input.strip():
        continue
        
    print("Mechanic is thinking...")
    
    # Send the message to the ongoing chat history session
    response = chat.send_message(user_input)
    
    # Print out what the mechanic says
    print(f"\nMotoMechanic: {response.text}\n")