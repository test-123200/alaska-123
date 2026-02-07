import asyncio
import cv2
import time
import os
import secrets
from supabase import Client

# Log helper
log_file = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'agent.log')
def log(msg):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[Video] {msg}\n")
        print(f"[Video] {msg}")
    except:
        pass

class VideoRecorderService:
    def __init__(self, supabase: Client, employee_id: str):
        self.supabase = supabase
        self.employee_id = employee_id
        self.is_recording = False
        self.default_duration = 10
        self.cache_dir = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'videos')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.max_cache_videos = 2

    async def start(self):
        log("Service started.")
        await self.sync_cache()

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
            
            for cmd in response.data:
                await self.handle_command(cmd)
        except Exception as e:
            log(f"Poll error: {e}")

    async def handle_command(self, cmd):
        if self.is_recording:
            return
        
        try:
            self.supabase.table("commands").update({"status": "PROCESSING"}).eq("id", cmd["id"]).execute()
        except:
            pass

        duration = await self.get_duration()
        log(f"Recording {duration}s clip...")
        success = await self.record_video(duration)
        
        try:
            status = "EXECUTED" if success else "ERROR"
            self.supabase.table("commands").update({"status": status}).eq("id", cmd["id"]).execute()
        except:
            pass

    async def record_video(self, duration):
        self.is_recording = True
        
        filename = f"clip_{int(time.time())}_{secrets.token_hex(4)}.avi"
        cache_path = os.path.join(self.cache_dir, filename)

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            log("Error: No camera.")
            self.is_recording = False
            return False

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        codec = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(cache_path, codec, 20.0, (width, height))
        
        start_time = time.time()
        try:
            while int(time.time() - start_time) < duration:
                ret, frame = cap.read()
                if ret:
                    out.write(frame)
                await asyncio.sleep(0.01)
        finally:
            cap.release()
            out.release()

        log(f"Recorded: {filename}")
        self.prune_cache()

        uploaded = await self.upload_file(cache_path, filename)
        if uploaded:
            log(f"Uploaded: {filename}")
            self.delete_file(cache_path)
        else:
            log(f"Cached: {filename}")

        self.is_recording = False
        return True

    async def upload_file(self, file_path, filename):
        try:
            with open(file_path, 'rb') as f:
                storage_path = f"{self.employee_id}/{filename}"
                self.supabase.storage.from_("videos").upload(
                    file=f, 
                    path=storage_path, 
                    file_options={"content-type": "video/x-msvideo", "upsert": "true"}
                )
            
            self.supabase.table("videos").insert({
                "employee_id": self.employee_id,
                "storage_path": storage_path,
                "url": storage_path 
            }).execute()
            return True
        except Exception as e:
            log(f"Upload error: {e}")
            return False

    async def sync_cache(self):
        try:
            files = [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.avi')]
            for fpath in files:
                fname = os.path.basename(fpath)
                if await self.upload_file(fpath, fname):
                    log(f"Synced: {fname}")
                    self.delete_file(fpath)
        except Exception as e:
            log(f"Sync error: {e}")

    def prune_cache(self):
        try:
            files = sorted(
                [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.avi')],
                key=os.path.getctime
            )
            if len(files) > self.max_cache_videos:
                for f in files[:len(files) - self.max_cache_videos]:
                    self.delete_file(f)
        except:
            pass

    def delete_file(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
