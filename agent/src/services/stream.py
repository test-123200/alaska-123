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
        self.cache_dir = os.path.join(os.getenv('APPDATA'), 'AlaskaCache', 'videos')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.max_cache_videos = 2

    async def start(self):
        print("VideoRecorderService started.")
        
        # 1. Record Startup Video (15s)
        print("Recording Startup Video (15s)...")
        await self.record_video_task(duration=15, is_startup=True)

        # 2. Try sync
        await self.sync_cache()

        # 3. Listen for commands
        print("Waiting for 'RECORD_CLIP' commands...")
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
                await self.handle_command(cmd)
        except Exception as e:
            # print(f"Error polling: {e}")
            pass

    async def handle_command(self, cmd):
        # Update status processing
        try:
            self.supabase.table("commands").update({"status": "PROCESSING"}).eq("id", cmd["id"]).execute()
        except:
            pass # Might be offline

        duration = await self.get_duration()
        success = await self.record_video_task(duration, cmd_id=cmd["id"])
        
        if success:
             try:
                self.supabase.table("commands").update({"status": "EXECUTED"}).eq("id", cmd["id"]).execute()
             except:
                 pass
        else:
             try:
                self.supabase.table("commands").update({"status": "ERROR"}).eq("id", cmd["id"]).execute()
             except:
                 pass

    async def record_video_task(self, duration, cmd_id=None, is_startup=False):
        if self.is_recording:
            return False
        
        self.is_recording = True
        
        filename = f"clip_{'startup_' if is_startup else ''}{int(time.time())}_{secrets.token_hex(4)}.avi"
        cache_path = os.path.join(self.cache_dir, filename)

        codec = cv2.VideoWriter_fourcc(*'XVID')
        fps = 20.0
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("Error: No camera.")
            self.is_recording = False
            return False

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(cache_path, codec, fps, (width, height))
        
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

        self.is_recording = False
        print(f"Video recorded: {filename}")
        
        # Prune older videos
        self.prune_cache()

        # Upload
        uploaded = await self.upload_file(cache_path, filename)
        if uploaded:
            print("Video uploaded.")
            self.delete_file(cache_path)
            return True
        else:
            print("Offline. Video cached.")
            return True # Successfully recorded (even if cached)

    async def upload_file(self, file_path, filename):
        try:
            with open(file_path, 'rb') as f:
                storage_path = f"{self.employee_id}/{filename}"
                self.supabase.storage.from_("videos").upload(
                    file=f, path=storage_path, file_options={"content-type": "video/x-msvideo"}
                )
            
            self.supabase.table("videos").insert({
                "employee_id": self.employee_id,
                "storage_path": storage_path,
                "url": storage_path 
            }).execute()
            return True
        except Exception:
            return False

    async def sync_cache(self):
        files = [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.avi')]
        for fpath in files:
            fname = os.path.basename(fpath)
            if await self.upload_file(fpath, fname):
                print(f"Synced cached video: {fname}")
                self.delete_file(fpath)
            else:
                break

    def prune_cache(self):
        files = sorted(
            [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.avi')],
            key=os.path.getctime
        )
        if len(files) > self.max_cache_videos:
            # Remove oldest
            to_remove = files[:len(files) - self.max_cache_videos]
            for f in to_remove:
                self.delete_file(f)

    def delete_file(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
