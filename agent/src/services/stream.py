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
        self.default_duration = 10

    async def start(self):
        print("VideoRecorderService started. Waiting for 'RECORD_CLIP' commands...")
        while True:
            await self.poll_commands()
            await asyncio.sleep(2)

    async def get_duration(self):
        try:
            response = self.supabase.table("employees").select("settings").eq("id", self.employee_id).single().execute()
            if response.data and response.data.get("settings"):
                return response.data["settings"].get("video_duration", self.default_duration)
        except:
            pass
        return self.default_duration

    async def poll_commands(self):
        try:
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
            return 
        
        self.is_recording = True
        
        # Fetch updated duration
        duration = await self.get_duration()
        print(f"Starting video clip recording ({duration}s) for command {cmd['id']}...")
        
        self.supabase.table("commands").update({"status": "PROCESSING"}).eq("id", cmd["id"]).execute()

        filename = f"clip_{int(time.time())}_{secrets.token_hex(4)}.avi"
        codec = cv2.VideoWriter_fourcc(*'XVID')
        fps = 20.0
        
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("Error: Could not open camera.")
            self.supabase.table("commands").update({"status": "ERROR", "payload": {"error": "No camera"}}).eq("id", cmd["id"]).execute()
            self.is_recording = False
            return

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
                await asyncio.sleep(0.01)
        finally:
            cap.release()
            out.release()
            cv2.destroyAllWindows()

        print(f"Recording complete: {filename}. Uploading...")

        try:
            with open(filename, 'rb') as f:
                storage_path = f"{self.employee_id}/{filename}"
                self.supabase.storage.from_("videos").upload(
                    file=f,
                    path=storage_path,
                    file_options={"content-type": "video/x-msvideo"}
                )
            
            self.supabase.table("videos").insert({
                "employee_id": self.employee_id,
                "storage_path": storage_path,
                "url": storage_path 
            }).execute()

            self.supabase.table("commands").update({"status": "EXECUTED"}).eq("id", cmd["id"]).execute()
            print("Video uploaded and command executed.")

        except Exception as e:
            print(f"Error uploading video: {e}")
            self.supabase.table("commands").update({"status": "ERROR", "payload": {"error": str(e)}}).eq("id", cmd["id"]).execute()
        
        finally:
            if os.path.exists(filename):
                os.remove(filename)
            self.is_recording = False
