import subprocess
import sys
import webbrowser
import time

def start_app():
    # Start the Streamlit server invisibly in the background
    process = subprocess.Popen(
        ["streamlit", "run", "main.py", "--client.toolbarMode=hidden"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait a moment for the local port server to spin up
    time.sleep(3)
    # Automatically boot open your browser directly to the dashboard interface
    webbrowser.open("http://localhost:8501")
    
    # Keep the script alive while the engine runs
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()

if __name__ == "__main__":
    start_app()