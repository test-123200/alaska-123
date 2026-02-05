import asyncio
import cv2
import time
import os
import secrets
from supabase import Client

class VideoRecorderService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.is_recording = False

    async def start(self):
        print("VideoRecorderService started. Waiting for 'RECORD_CLIP' commands...")
        # In a real scenario, the ControlService would handle the command dispatching, 
        # but to keep it simple, we can listen for specific commands here or better yet,
        # have the ControlService trigger this. 
        #
        # For this architecture, let's assume ControlService will write to a shared state or 
        # we act on specific command rows if ControlService doesn't handle them.
        #
        # ACTUALLY: The cleanest way is for ControlService to see "RECORD_CLIP", and call a method on this instance if they were shared.
        # Since they are separate objects in main.py, let's just duplicate the polling logic for simplicity OR
        # rely on the logic that this service is "always on" and we just need a mechanism to trigger.
        
        # Let's poll for a specific command status or use a shared event. 
        # Since I can't easily change main.py architecture right now without reloading it, 
        # I'll implement polling for 'RECORD_CLIP' commands specifically here.
        
        while True:
            await self.poll_commands()
            await asyncio.sleep(2)

    async def poll_commands(self):
        try:
            # Look for RECORD_CLIP commands
            response = self.supabase.table("commands")\
                .select("*")\
                .eq("employee_id", self.employee_id)\
                .eq("command_type", "RECORD_CLIP")\
                .eq("status", "PENDING")\
                .execute()
            
            commands = response.data
            for cmd in commands:
                await self.record_clip(cmd)
        except Exception as e:
            print(f"Error polling video commands: {e}")

    async def record_clip(self, cmd):
        if self.is_recording:
            return # Already recording
        
        self.is_recording = True
        print(f"Starting video clip recording for command {cmd['id']}...")
        
        # Update status to processing
        self.supabase.table("commands").update({"status": "PROCESSING"}).eq("id", cmd["id"]).execute()

        duration = 10 # seconds
        filename = f"clip_{int(time.time())}_{secrets.token_hex(4)}.avi"
        # Use XVID for Windows compatibility usually
        codec = cv2.VideoWriter_fourcc(*'XVID')
        fps = 20.0
        
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("Error: Could not open camera.")
            self.supabase.table("commands").update({"status": "ERROR", "payload": {"error": "No camera"}}).eq("id", cmd["id"]).execute()
            self.is_recording = False
            return

        # Get actual dimensions
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        out = cv2.VideoWriter(filename, codec, fps, (width, height))
        
        start_time = time.time()
        try:
            while int(time.time() - start_time) < duration:
                ret, frame = cap.read()
                if ret:
                    out.write(frame)
                else:
                    break
                await asyncio.sleep(0.01) # Small yield
        finally:
            cap.release()
            out.release()
            cv2.destroyAllWindows()

        print(f"Recording complete: {filename}. Uploading...")

        # Upload
        try:
            with open(filename, 'rb') as f:
                storage_path = f"{self.employee_id}/{filename}"
                self.supabase.storage.from_("videos").upload(
                    file=f,
                    path=storage_path,
                    file_options={"content-type": "video/x-msvideo"}
                )
            
            # Insert into videos table
            self.supabase.table("videos").insert({
                "employee_id": self.employee_id,
                "storage_path": storage_path,
                "url": storage_path 
            }).execute()

            # Mark command done
            self.supabase.table("commands").update({"status": "EXECUTED"}).eq("id", cmd["id"]).execute()
            print("Video uploaded and command executed.")

        except Exception as e:
            print(f"Error uploading video: {e}")
            self.supabase.table("commands").update({"status": "ERROR", "payload": {"error": str(e)}}).eq("id", cmd["id"]).execute()
        
        finally:
            if os.path.exists(filename):
                os.remove(filename)
            self.is_recording = False
